import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as path from 'path';
import { Construct } from 'constructs';

export class LambdaStack extends cdk.Stack {
  public readonly fn: lambda.Function;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.fn = new lambda.Function(this, 'Lambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lambda_function.handler',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../../lambdas/chatbot_bot')
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

    new cdk.CfnOutput(this, 'LambdaArn', {
      value: this.fn.functionArn,
      description: 'Lambda function ARN',
    });
    new cdk.CfnOutput(this, 'LambdaUrl', {
      value: fnUrl.url,
      description: 'Lambda Function URL for Chatwoot webhook',
    });
  }
}
