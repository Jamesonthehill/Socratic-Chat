# Combined Render Blueprint deployment

The root `render.yaml` provisions one starter Render web service. It bundles
the frontend and runs the platform gateway plus private Socratic, Reflections,
and SDL engine processes on loopback ports. It provisions no persistent disk or
Render database. The shared `PLATFORM_SERVICE_TOKEN` authenticates internal
engine requests, and the platform health check reports the health of all four
processes.

## Deploy

1. Push the changes to the GitHub branch Render will use.
2. Choose **New → Blueprint**, select the repository and branch, and use root
   `render.yaml`. Confirm the instance plan and no-disk configuration before
   creating the Blueprint.
3. Supply an existing free-tier PostgreSQL/pgvector `DATABASE_URL`,
   `GROQ_API_KEY`, and, if using existing OpenAI embedding features,
   `OPENAI_API_KEY` for `cluball-reflections`. The other services reference these
   values. This file does not provision or change an external provider's plan.
   OpenAI API usage is billed separately; leave its key blank if no paid API
   usage is permitted. Features requiring that key will be unavailable. Groq
   requests must remain within your account's free limits.
4. Supply the platform's HTTPS origin for `FRONTEND_URL`,
   `CORS_ALLOWED_ORIGINS`, and `LTI_PUBLIC_BASE_URL`. Enter credentials for your
   Canvas LTI version; unused optional LTI secrets can remain blank. Preserve
   existing auth configuration when adopting an existing platform service.
5. Check service health, sign in, and try representative assignments for each
   activity. Health checks do not prove model-provider or document-parser access.

## Free-tier limits

- The configured starter instance hosts all four processes. Check Render's
  current pricing and memory limits before deployment.
- A process health check does not prove model-provider or document-parser
  availability. Retry a request after a cold start has completed.
- All local files are ephemeral, including SDL uploads, model downloads, and
  pipeline traces. PostgreSQL records persist at your external database, but
  records referencing lost local files do not make those files durable.
- Reflections embedding models and SDL's Docling/PyTorch parsing may exceed free
  instance memory. Successful execution on free instances is not established;
  this Blueprint does not automatically upgrade a service when it fails.
- Render bandwidth and build quotas also apply. To enforce no payments, use a
  workspace without a payment method and verify the account's billing settings.
  API keys and the external database have their own independent billing rules.

See https://render.com/docs/free for Render's current limits.

## Existing services and database

Existing services can be adopted by the Blueprint. Changing this file does not
modify live Render resources. Review the Render dashboard before replacing or
removing an existing deployment.

Database migrations still run at startup. Reconcile legacy/shared RAG table
conflicts before deployment. Reflections needs the platform tables initialized;
if deploying against a fresh database, retry it after the platform migration.
All child engines restart with the combined service.

Validation covers the published Render JSON schema, service references, and
free-only resource configuration. Hosted builds, memory usage, provider calls,
Canvas launches, and full activity workflows still need validation on Render.
