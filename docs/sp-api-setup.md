# SP-API setup for the live market slice

Atlas reads the Amazon catalog through the Selling Partner API (SP-API)
Catalog Items search. It never writes to Amazon. You need four things in the
environment:

| Variable | What it is | Typical form |
|---|---|---|
| `SP_API_LWA_CLIENT_ID` | Your SP-API app's Login with Amazon (LWA) client identifier | `amzn1.application-oa2-client.…` |
| `SP_API_LWA_CLIENT_SECRET` | That app's LWA client secret | `amzn1.oa2-cs.v1.…` |
| `SP_API_REFRESH_TOKEN` | A refresh token from authorizing the app for your seller account | `Atzr|…` |
| `ATLAS_ALLOW_LIVE_MARKET` | Atlas's opt-in switch for live market calls | `1` |

Never put the first three in the repo, a `.env` file inside the repo, chat
messages, issues or logs. Atlas reads them from the process environment
only. It does not load `.env` files, and it never prints, stores or records
the values.

## Before you start

* **Seller account.** You need an Amazon seller account in the US
  marketplace (Seller Central). Self-authorized ("private") SP-API apps
  generally require a Professional selling plan. A KDP-only author account
  is not a Seller Central account.
* **Cost.** Catalog Items calls have no per-call fee. The seller plan itself
  may cost money.
* **Time.** Developer registration is reviewed by Amazon and can take from
  hours to several days.

## Sequence

Seller Central menu names change from time to time; the steps below follow
Amazon's current SP-API developer documentation at a practical level.

1. **Register as a developer.** In Seller Central, open *Apps and Services →
   Develop Apps*. Complete the developer profile as a **private developer**,
   building apps for your own organization only.
2. **Request the right data access.** Select the **Product Listing** role.
   That role covers Catalog Items, and Atlas needs nothing else. Do not
   request restricted roles involving personal data. Atlas only reads
   public catalog data.
3. **Wait for approval.** Amazon emails you when the developer profile is
   approved.
4. **Create the app client.** In *Develop Apps*, choose *Add new app client*.
   Use any name (for example "atlas-amazon research"), API type **SP-API**,
   and the Product Listing role. No AWS IAM user or ARN is needed: SP-API no
   longer requires AWS Signature V4.
5. **Copy the LWA credentials.** Open the app's *LWA credentials* (*View*).
   * The client identifier becomes `SP_API_LWA_CLIENT_ID`.
   * The client secret becomes `SP_API_LWA_CLIENT_SECRET`.

   Amazon requires client secrets to be rotated periodically. When it
   rotates, update the variable.
6. **Self-authorize to get a refresh token.** On the app, choose *Authorize*
   from the edit menu, then *Authorize app*. Copy the refresh token shown
   (`Atzr|…`) into `SP_API_REFRESH_TOKEN`. It does not expire on a timer,
   but it stops working if you revoke the authorization or the app.
7. **Set the variables for your user** (Windows PowerShell). Run the lines
   below in your own terminal, not through Claude:

   ```powershell
   [Environment]::SetEnvironmentVariable("SP_API_LWA_CLIENT_ID", "<paste>", "User")
   [Environment]::SetEnvironmentVariable("SP_API_LWA_CLIENT_SECRET", "<paste>", "User")
   [Environment]::SetEnvironmentVariable("SP_API_REFRESH_TOKEN", "<paste>", "User")
   [Environment]::SetEnvironmentVariable("ATLAS_ALLOW_LIVE_MARKET", "1", "User")
   ```

   Then fully restart the app or terminal that runs Atlas so it picks up the
   new environment. Keep a copy in your password manager. The repo needs
   none of it.
8. **Check prerequisites offline.** This makes no network call and prints
   only names and "set/missing":

   ```bash
   python scripts/record_live_market.py --prereqs
   ```

9. **Check auth.** This makes one LWA token exchange and no catalog call:

   ```bash
   python scripts/record_live_market.py --check
   ```

10. **Run the slice.** Ask for the live-validation follow-up, or run
    `--plan` and then `--run` yourself. The run makes 4 catalog calls (2 per
    scenario, first page only) into
    `tests/fixtures/recordings/live/market_v10/`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `--prereqs` shows `missing` after setting variables | The app or terminal was not restarted after `SetEnvironmentVariable` |
| `set, but does not look like an LWA client ID` | The app ID (`amzn1.sp.solution…`) or the secret was pasted instead of the client identifier |
| `LWA token exchange failed: HTTP 400 invalid_grant` | The refresh token is wrong, was revoked, or belongs to a different app |
| `LWA token exchange failed: HTTP 401 invalid_client` | The client ID and secret don't match, or the secret was rotated |
| Catalog call `http_403 Unauthorized` | The app lacks the Product Listing role, or is not authorized for this seller or marketplace |
| Catalog call `http_429 QuotaExceeded` | The rate limit was hit (5 requests/s). Atlas does not retry; rerun later into a fresh directory |

## Revoking access

To revoke the refresh token, open Seller Central → *Apps and Services →
Manage Your Apps* and remove the authorization. To retire the client
secret, delete or rotate it in *Develop Apps*. Then remove the user
environment variables.
