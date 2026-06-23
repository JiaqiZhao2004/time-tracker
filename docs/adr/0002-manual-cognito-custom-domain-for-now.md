---
status: accepted
---

# Keep the Cognito custom domain manual for now

Trace uses a manually configured Cognito managed-login custom domain, `cognito-auth.trace.royzhao.dev`, while SAM continues to manage the Cognito user pool, app client, original Cognito prefix domain, API authorizer, callback URLs, and CORS settings. This keeps the public branded sign-in domain working without forcing a risky CloudFormation resource import during the domain migration.

## Considered Options

- Keep using only the SAM-managed Cognito prefix domain, `time-tracker-jiaqizhao2004.auth.us-east-2.amazoncognito.com`. This is operationally simple but loses the branded auth domain.
- Import the existing custom domain into the SAM stack. This is the cleanest long-term ownership model, but the import path was brittle because the stack is deployed through SAM packaging and the existing custom domain was created manually.
- Leave the custom domain manual temporarily and configure the app to use it. This preserves the branded sign-in experience while keeping SAM deploys reliable.

## Future Move

The desired long-term state is for SAM to own the Cognito custom domain. During a planned maintenance window, delete the manually created Cognito custom domain, add an `AWS::Cognito::UserPoolDomain` resource with `CustomDomainConfig` and the ACM certificate ARN to `template.yaml`, and let the next SAM deploy create and manage `cognito-auth.trace.royzhao.dev`.

## Consequences

Until that future move, the DNS record for `cognito-auth.trace.royzhao.dev` and the Cognito custom domain configuration must be maintained manually. SAM-managed parameters should still include `https://trace.royzhao.dev` in callback URLs, logout URLs, and API CORS origins, and the frontend should use `VITE_COGNITO_DOMAIN=https://cognito-auth.trace.royzhao.dev`.
