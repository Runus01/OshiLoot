import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from "aws-cdk-lib";
import * as cloudfront from "aws-cdk-lib/aws-cloudfront";
import * as origins from "aws-cdk-lib/aws-cloudfront-origins";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as logs from "aws-cdk-lib/aws-logs";
import * as s3 from "aws-cdk-lib/aws-s3";
import type { Construct } from "constructs";
import { BACKEND_REPOSITORY, GITHUB_DEPLOY_ROLE, SSM_PREFIX } from "./names.ts";

// Sends every path without a file extension (/anime/52991) to index.html, so the React
// router can handle it. Runs only on the S3 behaviour, never on /api or /go.
const SPA_REWRITE = `
function handler(event) {
  var request = event.request;
  if (request.uri.indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}`;

export class AppStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const imageTag: string = this.node.tryGetContext("imageTag") ?? "latest";

    // Provisioned capacity stays inside DynamoDB's always-free 25 read + 25 write units.
    // On-demand mode is not covered by the free tier.
    const cacheTable = new dynamodb.Table(this, "CacheTable", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 5,
      writeCapacity: 5,
      timeToLiveAttribute: "ttl",
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const clicksTable = new dynamodb.Table(this, "ClicksTable", {
      partitionKey: { name: "pk", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "sk", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 5,
      writeCapacity: 5,
      removalPolicy: RemovalPolicy.RETAIN, // click history survives a teardown
    });

    // The whole backend (all four modules) is one function.
    const backend = new lambda.DockerImageFunction(this, "Backend", {
      code: lambda.DockerImageCode.fromEcr(
        ecr.Repository.fromRepositoryName(this, "BackendRepository", BACKEND_REPOSITORY),
        { tagOrDigest: imageTag },
      ),
      architecture: lambda.Architecture.X86_64,
      memorySize: 512,
      timeout: Duration.seconds(15),
      logGroup: new logs.LogGroup(this, "BackendLogs", {
        retention: logs.RetentionDays.TWO_WEEKS,
        removalPolicy: RemovalPolicy.DESTROY,
      }),
      environment: {
        STORAGE: "dynamodb",
        CACHE_TABLE: cacheTable.tableName,
        CLICKS_TABLE: clicksTable.tableName,
        SSM_PREFIX,
      },
    });
    cacheTable.grantReadWriteData(backend);
    clicksTable.grantWriteData(backend);
    backend.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ssm:GetParametersByPath"],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter${SSM_PREFIX.replace(/\/$/, "")}`,
          `arn:aws:ssm:${this.region}:${this.account}:parameter${SSM_PREFIX}*`,
        ],
      }),
    );

    // IAM auth + origin access control: only this CloudFront distribution can call the function.
    const backendUrl = backend.addFunctionUrl({ authType: lambda.FunctionUrlAuthType.AWS_IAM });

    const siteBucket = new s3.Bucket(this, "SiteBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const apiBehavior: cloudfront.BehaviorOptions = {
      origin: origins.FunctionUrlOrigin.withOriginAccessControl(backendUrl),
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      // Lambda Function URLs reject a forwarded Host header.
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
    };

    const distribution = new cloudfront.Distribution(this, "Site", {
      comment: "OshiLoot",
      defaultRootObject: "index.html",
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
        functionAssociations: [
          {
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
            function: new cloudfront.Function(this, "SpaRewrite", {
              code: cloudfront.FunctionCode.fromInline(SPA_REWRITE),
              runtime: cloudfront.FunctionRuntime.JS_2_0,
            }),
          },
        ],
      },
      additionalBehaviors: {
        "/api/*": apiBehavior,
        "/go/*": apiBehavior,
      },
    });

    // Let the GitHub Actions role upload the frontend build and refresh index.html.
    const deployRole = iam.Role.fromRoleName(this, "GithubDeployRole", GITHUB_DEPLOY_ROLE);
    siteBucket.grantReadWrite(deployRole);
    siteBucket.grantDelete(deployRole);
    distribution.grantCreateInvalidation(deployRole);

    new CfnOutput(this, "SiteBucketName", { value: siteBucket.bucketName });
    new CfnOutput(this, "DistributionId", { value: distribution.distributionId });
    new CfnOutput(this, "SiteUrl", { value: `https://${distribution.distributionDomainName}` });
  }
}
