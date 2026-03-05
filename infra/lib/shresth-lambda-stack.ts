import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { Construct } from 'constructs';

export class ShresthLambdaStack extends cdk.Stack {
  public readonly fn: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.fn = new lambda.DockerImageFunction(this, 'ShresthLambda', {
      architecture: lambda.Architecture.ARM_64,
      code: lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../../lambdas/shresth')
      ),
      timeout: cdk.Duration.seconds(30),
    });

    this.fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel'],
        resources: ['*'],
      })
    );

    const fnUrl = this.fn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    new cdk.CfnOutput(this, 'ShresthLambdaArn', {
      value: this.fn.functionArn,
      description: 'Shresth Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'ShresthLambdaUrl', {
      value: fnUrl.url,
      description: 'Shresth Lambda Function URL',
    });
  }
}
