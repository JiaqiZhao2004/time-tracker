# Use a shared public guest mode

Trace will offer guest exploration through a single shared server-backed Guest identity instead of a browser-only sandbox or per-visitor anonymous accounts. This keeps the experience simple and synced across devices without adding a new identity provider flow.

Guest visitors can log time entries against shared curated categories, but they cannot create or rename categories or edit the shared profile name. Those free-text controls stay visible in the UI as disabled affordances with explanatory hover notices, and the guest backend routes return `403` for the same mutations. This avoids making the app feel incomplete while reducing the abuse risk of globally visible public text.
