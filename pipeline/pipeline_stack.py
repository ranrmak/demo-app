from aws_cdk import aws_s3, Stage, Stack, CfnOutput, SecretValue, aws_logs, aws_iam
from aws_cdk import pipelines as _pipelines
from aws_cdk import aws_codebuild as _codebuild
from aws_cdk import aws_iam as _iam
from aws_cdk import aws_ecr as _ecr
from aws_cdk import aws_ssm as _ssm
from constructs import Construct

import uuid

from .lambda_stack import LambdaStack
from .BuildSpec import buildspec as buildContainerBuildSpec

image_tag = f'latest-{str(uuid.uuid4()).split("-")[-1]}'


class ApplicationStageLambda1(Stage):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        LambdaStack(self, 'Demo-Lambda1', image_tag)


class ApplicationStageLambda2(Stage):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        LambdaStack(self, 'Demo-Lambda2', image_tag)


class PipelineStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        ecr_repo = _ecr.Repository(self, "lambda_container_pipeline")

        ecr_output_name = CfnOutput(self, 'ecr_repo_name',
                                    value=ecr_repo.repository_name,
                                    export_name="ecr-repo-name")

        ecr_output_uri = CfnOutput(self, 'ecr_repo_uri',
                                   value=ecr_repo.repository_uri,
                                   export_name="ecr-repo-uri")

        github_repo = 'ziweizhou-sam/rca-demo'

        git_hub_commit = _pipelines.CodePipelineSource.git_hub(
            github_repo,
            "main",
            authentication=SecretValue.secrets_manager(
                "lambda_container_cdk_pipeline_github", json_field='github')
        )

        pipeline = _pipelines.CodePipeline(self, "Container_Pipeline",
                                           synth=_pipelines.ShellStep("Synth",
                                                                      input=git_hub_commit,
                                                                      commands=[
                                                                          "npm install -g aws-cdk && pip install -r requirements.txt",
                                                                          "cdk synth",
                                                                          "pytest unittests"]
                                                                      )
                                           )

        build_spec = _codebuild.BuildSpec.from_object(buildContainerBuildSpec)

        log_bucket = aws_s3.Bucket(self, "rca_demo", bucket_name="rca-demo-02")
        log_bucket.add_to_resource_policy(aws_iam.PolicyStatement(
            actions=['s3:*'],
            resources=[log_bucket.arn_for_objects('*')],
            principals=[aws_iam.AccountPrincipal('844041478127')]
        ))

        build_container_project = _pipelines.CodeBuildStep("ContainerBuild",
            build_environment=_codebuild.BuildEnvironment(
                build_image=_codebuild.LinuxBuildImage.STANDARD_7_0,
                privileged=True
            ),
            input=git_hub_commit,
            partial_build_spec=build_spec,
            commands=[],
            env={
                "IMAGE_TAG": image_tag,
                "AWS_ACCOUNT_ID": self.account,
                "IMAGE_REPO_NAME": ecr_repo.repository_uri
            },
            logging=_codebuild.LoggingOptions(
                s3=_codebuild.S3LoggingOptions(
                    bucket=log_bucket,
                    prefix="build-log"),
                cloud_watch=_codebuild.CloudWatchLoggingOptions(
                    log_group=aws_logs.LogGroup(self,"rca_demo_log_group"),
                    prefix="build-log")
            )
        )

        lambda_function1 = ApplicationStageLambda1(self, 'Container-CDK-Pipeline-Lambda-Stage1')
        lambda_function_stage1 = pipeline.add_stage(lambda_function1, pre=[build_container_project])

        # lambda_function2 = ApplicationStageLambda2(self, 'Container-CDK-Pipeline-Lambda-Stage2')
        # lambda_function_stage2 = pipeline.add_stage(lambda_function2, pre=[buildContainerProject])

        pipeline.build_pipeline()

        ecr_repo_actions = ["ecr:PutImage",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:CompleteLayerUpload",
                            "ecr:InitiateLayerUpload",
                            "ecr:UploadLayerPart"]

        for perm in ecr_repo_actions:
            ecr_repo.grant(build_container_project, perm)

        _iam.Grant.add_to_principal(

            actions=["ecr:GetAuthorizationToken"],
            resource_arns=["*"],
            grantee=build_container_project
        )
