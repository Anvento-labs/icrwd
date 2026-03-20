import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { Construct } from 'constructs';

export class SupportLambdaStack extends cdk.Stack {
  public readonly fn: lambda.DockerImageFunction;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.fn = new lambda.DockerImageFunction(this, 'SupportLambda', {
      architecture: lambda.Architecture.ARM_64,
      code: lambda.DockerImageCode.fromImageAsset(
        path.join(__dirname, '../../lambdas/support')
      ),
      timeout: cdk.Duration.seconds(30),
    });

    this.fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['bedrock:InvokeModel', 'bedrock:Retrieve'],
        resources: ['*'],
      })
    );

    const fnUrl = this.fn.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
    });

    new cdk.CfnOutput(this, 'SupportLambdaArn', {
      value: this.fn.functionArn,
      description: 'Support Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'SupportLambdaUrl', {
      value: fnUrl.url,
      description: 'Support Lambda Function URL',
    });
  }
}
