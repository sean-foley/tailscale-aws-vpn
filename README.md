# Tailscale Exit Node on AWS

AWS CDK project that deploys a t4g.nano EC2 instance configured as a Tailscale exit node.

## What Gets Created

- VPC with a public subnet (10.0.0.0/16)
- Security group allowing SSH from your home IP only + Tailscale UDP
- t4g.nano EC2 instance (ARM64, ~$3/month)
- Elastic IP for a static public address
- ED25519 key pair (stored in AWS Systems Manager)

## Prerequisites

1. **AWS CLI** configured with credentials:
   ```bash
   aws configure
   ```

2. **Node.js** (required for CDK CLI):
   ```bash
   brew install node  # macOS
   ```

3. **AWS CDK CLI**:
   ```bash
   npm install -g aws-cdk
   ```

4. **Python 3.8+** with pip

## Setup

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Bootstrap CDK (one-time per account/region):
   ```bash
   cdk bootstrap aws://ACCOUNT_ID/us-west-2
   ```
   Or let it auto-detect:
   ```bash
   cdk bootstrap
   ```

## Deploy

Get your home IP and deploy:

```bash
# Find your home IP
curl ifconfig.me

# Deploy (replace with your actual IP)
cdk deploy -c home_ip=YOUR_HOME_IP
```

Or use environment variable:
```bash
export HOME_IP=$(curl -s ifconfig.me)
cdk deploy
```

## After Deployment

1. **Download the SSH key** (from the CDK output):
   ```bash
   aws ssm get-parameter \
     --name /ec2/keypair/KEY_PAIR_ID \
     --with-decryption \
     --query Parameter.Value \
     --output text > tailscale-key.pem
   chmod 400 tailscale-key.pem
   ```

2. **SSH into the instance**:
   ```bash
   ssh -i tailscale-key.pem ec2-user@ELASTIC_IP
   ```

3. **Start Tailscale as exit node**:
   ```bash
   sudo tailscale up --advertise-exit-node
   ```

4. **Authenticate**: Open the URL provided and log in to your Tailscale account.

5. **Approve the exit node**:
   - Go to https://login.tailscale.com/admin/machines
   - Find your new machine
   - Click `...` menu → **Edit route settings**
   - Enable **"Use as exit node"**

6. **Use the exit node** on your devices:
   ```bash
   sudo tailscale up --exit-node=tailscale-exit-node
   ```

## Verify It's Working

From a client using the exit node:
```bash
curl ifconfig.me
```
Should return your AWS Elastic IP.

## Cleanup

To delete all resources:
```bash
cdk destroy
```

## Cost

| Resource | Monthly Cost |
|----------|--------------|
| t4g.nano | ~$3.07 |
| Elastic IP (attached) | Free |
| Data transfer | ~$0.09/GB after free tier |

**Total: ~$3-5/month** for light usage

## Troubleshooting

**Can't SSH?**
- Verify your home IP hasn't changed
- Check the security group in AWS Console
- Ensure the instance is running

**Tailscale not working?**
- Wait 2-3 minutes after deployment for user data to complete
- Check: `cat /var/log/tailscale-setup-complete`
- Check Tailscale status: `sudo tailscale status`

**Update home IP?**
- Redeploy with new IP: `cdk deploy -c home_ip=NEW_IP`
