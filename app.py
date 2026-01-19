#!/usr/bin/env python3
import os
import aws_cdk as cdk
from tailscale_stack import TailscaleExitNodeStack

app = cdk.App()

# Get home IP from context or environment variable
home_ip = app.node.try_get_context("home_ip") or os.environ.get("HOME_IP")

TailscaleExitNodeStack(
    app,
    "TailscaleExitNodeStack",
    home_ip=home_ip,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2"),
    ),
)

app.synth()
