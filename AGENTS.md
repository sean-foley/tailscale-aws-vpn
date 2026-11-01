# AGENTS.md

Guidance for AI coding agents working in this repo.

## Project

AWS CDK (Python) app that deploys a single t4g.nano EC2 instance (Amazon Linux 2023, ARM64) running Tailscale as an exit node. Everything lives in two files:

- `app.py` - CDK entry point; reads `home_ip` from context or `HOME_IP` env var
- `tailscale_stack.py` - VPC, security group, key pair, instance, user data, Elastic IP

## This is a public repo

Never commit account IDs, IP addresses, instance/key IDs, auth keys, or private keys. Pass environment-specific values via CDK context or environment variables. `cdk.context.json` and `cdk.out/` are gitignored because they contain account details.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk synth -c home_ip=<IP>
cdk diff -c home_ip=<IP>      # always diff before deploying
cdk deploy -c home_ip=<IP>
```

Default region is `us-west-2` (override with `CDK_DEFAULT_REGION`).

## Things that will bite you

- **Deploys can replace the instance.** The AMI is looked up as "latest AL2023 ARM64" at deploy time, and `user_data_causes_replacement=True`, so a new AMI or any user data change restacks the instance. This is intentional (immutable restacks), but run `cdk diff` first and expect a few minutes of exit-node downtime.
- **A restacked instance needs manual Tailscale auth.** User data installs Tailscale but does not log in. After a restack, someone must run `sudo tailscale up --advertise-exit-node`, open the login URL, approve the exit node in the admin console, and delete the old offline machine.
- **t4g.nano has ~420MB usable RAM.** `dnf` gets OOM-killed without the swap file created at the top of user data. Keep the swap step before any `dnf` command; Tailscale auto-update also runs dnf.
- **User data runs once, on first boot.** Changes only take effect on a new instance.
- **SSH is restricted to `home_ip`.** If the deployer's IP changes, SSH times out until redeployed with the new IP.

## Maintenance model

Tailscale updates itself (`tailscale set --auto-update`). OS/AMI updates happen by restacking onto the newest AMI. Prefer restacks over in-place patching when making changes.
