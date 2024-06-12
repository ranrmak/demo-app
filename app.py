#!/usr/bin/env python3

from aws_cdk import App

#from pipeline.ecr_repo import ECRRepoDeploy
from pipeline.pipeline_stack import PipelineStack

app = App()

PipelineStack(app, "cdk-pipelines-demo")

app.synth()
