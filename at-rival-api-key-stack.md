adding a "Generate API Key" feature for @TheRival fits perfectly into that ecosystem.

When building a decoupled architecture, the web app (the AHA stack) acts as the issuer and validator of the key, while the background robot script is the consumer.

Here is how you can implement a secure, reactive generate_rival_api_key button natively using Astro, HTMX, and Tailwind CSS.

1. The Database Setup (Storing the Key securely)
   You should never store API keys in plain text in your database. If someone gains read-access to your database, they can steal the key and masquerade as the bot. Instead, store a cryptographic hash of the key (like a password) using SHA-256.

Run this update on your users table:

```
ALTER TABLE users ADD COLUMN api_key_hash VARCHAR(64);
```

2. The Backend Handler (Astro Endpoint / Server Route)
   Create an Astro API route or server-side endpoint (e.g., src/pages/api/admin/generate-key.ts) that handles the generation logic when triggered by HTMX.

#### gernerate-key.ts

```
import type { APIRoute } from 'astro';
import { createHash, randomBytes } from 'crypto';
import { db } from '../../../db'; // Your database client connection

export const POST: APIRoute = async ({ request }) => {
  // 1. Ensure the requesting user is an authorized Admin
  // (Insert your session/auth verification check here)

  // 2. Generate a secure, human-readable random API key prefix + string
  const rawKey = `rival_${randomBytes(24).toString('hex')}`;

  // 3. Hash the key using SHA-256 before storing it
  const hashedKey = createHash('sha256').update(rawKey).digest('hex');

  // 4. Update the bot's user account record in your PostgreSQL instance
  await db.query(
    'UPDATE users SET api_key_hash = $1 WHERE username = $2',
    [hashedKey, 'TheRival']
  );

  // 5. Return an HTML partial directly to HTMX to update the UI
  // The raw key is shown ONCE here. It cannot be recovered from the DB again.
  return new Response(`
    <div class="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800 space-y-2">
      <p class="font-bold">⚠️ Copy this key now. You will not be able to see it again:</p>
      <div class="flex items-center space-x-2 bg-white p-2 border rounded font-mono text-xs select-all break-all">
        ${rawKey}
      </div>
      <p class="text-xs text-gray-500">Save this directly to your bot environment config as <code>RIVAL_API_KEY</code>.</p>
    </div>'
  `, {
    headers: { 'Content-Type': 'text/html' }
  });
};
```

####

#### The Front-End Component (Astro +HTMX)

```
---
// src/pages/admin/dashboard.astro
---
<div class="p-6 bg-white border border-gray-200 rounded-xl max-w-xl shadow-sm">
  <h2 class="text-lg font-semibold text-gray-900">@TheRival Bot Integration</h2>
  <p class="text-sm text-gray-500 mt-1 mb-4">
    Manage authentication credentials for the decoupled machine learning and persona runner.
  </p>

  <!-- Container where the generated key message will swap into view -->
  <div id="api-key-container" class="mb-4">
    <div class="text-sm text-gray-500 bg-gray-50 p-4 rounded-lg border border-dashed text-center">
      No active key displayed. Generating a new key will instantly invalidate any previous bot credentials.
    </div>
  </div>

  <!-- HTMX Powered Button -->
  <button
    hx-post="/api/admin/generate-key"
    hx-target="#api-key-container"
    hx-swap="innerHTML"
    hx-indicator="#loading-spinner"
    class="w-full sm:w-auto px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded-lg transition shadow-sm inline-flex items-center justify-center space-x-2 cursor-pointer"
  >
    <span>Generate New Rival API Key</span>
    <span id="loading-spinner" class="htmx-indicator animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full"></span>
  </button>
</div>
```

####

#### How validation works

How Validation Works When the Bot Calls In
When your separate Python bot engine finishes calculating predictions and executes its POST /api/v1/contest/submissions call, it sends the raw token string inside its HTTP headers:

Authorization: Bearer rival_8a2f3c...

Your web server interceptor handles validation safely using a quick string lookup:

Extract the raw string from the header.

Hash that incoming string using crypto.createHash('sha256').

Compare that resulting hash against the api_key_hash field saved inside the TheRival user row in PostgreSQL.

If they match, the request is fully authenticated, and your script can process the bot's incoming contest data.

####
