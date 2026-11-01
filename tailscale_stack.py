from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
)
from constructs import Construct


class TailscaleExitNodeStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, home_ip: str = None, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Validate home IP is provided
        if not home_ip:
            raise ValueError(
                "home_ip is required. Pass it via context: cdk deploy -c home_ip=YOUR_IP "
                "or set HOME_IP environment variable"
            )

        # Create VPC with public subnet only
        vpc = ec2.Vpc(
            self,
            "TailscaleVpc",
            vpc_name="tailscale-exit-node-vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=1,
            nat_gateways=0,  # No NAT gateway needed (saves cost)
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        # Create security group
        security_group = ec2.SecurityGroup(
            self,
            "TailscaleSG",
            security_group_name="tailscale-exit-node-sg",
            vpc=vpc,
            description="Security group for Tailscale exit node",
            allow_all_outbound=True,
        )

        # Allow SSH from home IP only
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(f"{home_ip}/32"),
            connection=ec2.Port.tcp(22),
            description=f"SSH from home IP ({home_ip})",
        )

        # Allow Tailscale UDP (helps with direct connections)
        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.udp(41641),
            description="Tailscale WireGuard UDP",
        )

        # User data script to install and configure Tailscale
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "#!/bin/bash",
            "set -e",
            "",
            "# Add a 1GB swap file: t4g.nano has 512MB RAM and dnf gets OOM-killed without it",
            "dd if=/dev/zero of=/swapfile bs=1M count=1024",
            "chmod 600 /swapfile",
            "mkswap /swapfile",
            "swapon /swapfile",
            "echo '/swapfile swap swap defaults 0 0' >> /etc/fstab",
            "",
            "# Install Tailscale",
            "dnf config-manager --add-repo https://pkgs.tailscale.com/stable/amazon-linux/2023/tailscale.repo",
            "dnf install tailscale -y",
            "",
            "# Enable and start Tailscale",
            "systemctl enable --now tailscaled",
            "",
            "# Enable IP forwarding for exit node functionality",
            "echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/99-tailscale.conf",
            "echo 'net.ipv6.conf.all.forwarding = 1' >> /etc/sysctl.d/99-tailscale.conf",
            "sysctl -p /etc/sysctl.d/99-tailscale.conf",
            "",
            "# Let Tailscale keep itself up to date (installs updates via dnf)",
            "tailscale set --auto-update",
            "",
            "# Marker file indicating setup is complete",
            "touch /var/log/tailscale-setup-complete",
        )

        # Create key pair (CDK will manage this)
        key_pair = ec2.KeyPair(
            self,
            "TailscaleKeyPair",
            key_pair_name="tailscale-exit-node-key",
            type=ec2.KeyPairType.ED25519,
        )

        # Look up latest Amazon Linux 2023 ARM64 AMI
        ami = ec2.MachineImage.latest_amazon_linux2023(
            cpu_type=ec2.AmazonLinuxCpuType.ARM_64,
        )

        # Create the EC2 instance
        instance = ec2.Instance(
            self,
            "TailscaleInstance",
            instance_name="tailscale-exit-node",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T4G,
                ec2.InstanceSize.NANO,
            ),
            machine_image=ami,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=security_group,
            key_pair=key_pair,
            user_data=user_data,
            # User data only runs on first boot, so changes must restack the instance
            user_data_causes_replacement=True,
            # Require IMDSv2 for better security
            require_imdsv2=True,
        )

        # Allocate and associate an Elastic IP for a static public IP
        eip = ec2.CfnEIP(
            self,
            "TailscaleEIP",
            domain="vpc",
            tags=[{"key": "Name", "value": "tailscale-exit-node-eip"}],
        )

        ec2.CfnEIPAssociation(
            self,
            "TailscaleEIPAssociation",
            eip=eip.ref,
            instance_id=instance.instance_id,
        )

        # Outputs
        CfnOutput(
            self,
            "InstanceId",
            value=instance.instance_id,
            description="EC2 Instance ID",
        )

        CfnOutput(
            self,
            "ElasticIP",
            value=eip.ref,
            description="Elastic IP address",
        )

        CfnOutput(
            self,
            "KeyPairId",
            value=key_pair.key_pair_id,
            description="Key Pair ID - retrieve private key from AWS Systems Manager Parameter Store",
        )

        CfnOutput(
            self,
            "SSHCommand",
            value=f"ssh -i tailscale-key.pem ec2-user@{eip.ref}",
            description="SSH command (after downloading the key)",
        )

        CfnOutput(
            self,
            "GetKeyCommand",
            value=f"aws ssm get-parameter --name /ec2/keypair/{key_pair.key_pair_id} --with-decryption --query Parameter.Value --output text > tailscale-key.pem && chmod 400 tailscale-key.pem",
            description="Command to download the SSH private key",
        )
