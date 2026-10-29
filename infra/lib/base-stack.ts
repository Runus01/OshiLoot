import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from "aws-cdk-lib";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as iam from "aws-cdk-lib/aws-iam";
import type { Construct } from "constructs";
import { BACKEND_REPOSITORY, GITHUB_DEPLOY_ROLE } from "./names.ts";

const GITHUB_OIDC_URL = "https://token.actions.githubusercontent.com";

export class BaseStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const githubRepo: string = this.node.getContext("githubRepo");
    if (!/^[\w.-]+\/[\w.-]+$/.test(githubRepo) || githubRepo.startsWith("YOUR_GITHUB_USERNAME")) {
      throw new Error(
        'Set "githubRepo" in infra/cdk.json to "<your-github-username>/oshiloot" ' +
          "(or pass -c githubRepo=...) before deploying OshiLootBase.",
      );
    }

    // Each push stores one image; keep only the last five so storage stays at a few cents.
    const repository = new ecr.Repository(this, "BackendRepository", {
      repositoryName: BACKEND_REPOSITORY,
      imageScanOnPush: true,
      lifecycleRules: [{ maxImageCount: 5 }],
      removalPolicy: RemovalPolicy.DESTROY,
      emptyOnDelete: true,
    });

    // An AWS account can hold only one provider for this URL. If you already have one,
    // deploy with -c createGithubOidcProvider=false to reuse it.
    const createProvider = this.node.tryGetContext("createGithubOidcProvider") !== false
      && this.node.tryGetContext("createGithubOidcProvider") !== "false";
    const provider = createProvider
      ? new iam.OidcProviderNative(this, "GithubOidc", {
          url: GITHUB_OIDC_URL,
          clientIds: ["sts.amazonaws.com"],
        })
      : iam.OidcProviderNative.fromOidcProviderArn(
          this,
          "GithubOidc",
          `arn:aws:iam::${this.account}:oidc-provider/token.actions.githubusercontent.com`,
        );

    // Only workflows running on this repo's main branch can assume this role.
    const deployRole = new iam.Role(this, "GithubDeployRole", {
      roleName: GITHUB_DEPLOY_ROLE,
      maxSessionDuration: Duration.hours(1),
      assumedBy: new iam.WebIdentityPrincipal(provider.oidcProviderArn, {
        StringEquals: { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
        StringLike: { "token.actions.githubusercontent.com:sub": `repo:${githubRepo}:ref:refs/heads/main` },
      }),
    });

    repository.grantPullPush(deployRole);

    // Lets the deploy workflow sign in to ECR Public, so pulls of the Python and Lambda
    // adapter base images get the authenticated rate limit instead of the anonymous one.
    // The token only reads public images; it grants nothing in this account.
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecr-public:GetAuthorizationToken", "sts:GetServiceBearerToken"],
        resources: ["*"],
      }),
    );

    // `cdk deploy` works by assuming the roles `cdk bootstrap` created.
    deployRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["sts:AssumeRole"],
        resources: [`arn:aws:iam::${this.account}:role/cdk-*`],
      }),
    );

    new CfnOutput(this, "DeployRoleArn", {
      value: deployRole.roleArn,
      description: "Save as the AWS_DEPLOY_ROLE_ARN repository variable on GitHub",
    });
    new CfnOutput(this, "RepositoryUri", { value: repository.repositoryUri });
  }
}
