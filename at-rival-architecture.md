You should absolutely build @TheRival as a separate app/microservice that interacts with your site via API, rather than embedding it directly into your core site architecture.

While you can (and should) still use Ollama to power the bot's conversational persona, that LLM engine should live inside the bot's own isolated environment, not on your main web server.

Here is exactly why decoupling @TheRival is the right architectural move.

1. The "Fair Play" Architecture (Dogfooding)
   If @TheRival is going to boast about beating humans, it needs to play by the same rules. By building it as a separate client, you force the AI to interact with your site exactly like a human would—by hitting your public or private API endpoints (e.g., POST /api/v1/predictions or POST /api/v1/forum/comment).

This proves to your users that the bot isn't "cheating" through direct database manipulation. It authenticates, reads the available data, and submits its picks before the deadline, just like they do.

2. Resource Isolation (Don't Crash the Site)
   Machine learning and LLMs are incredibly resource-heavy. If you embed Ollama and a Monte Carlo simulation engine directly into your main web application:

When the bot generates a complex, snarky response, it spikes CPU/GPU usage.

When it runs 10,000 simulations for the Tuesday prediction drop, it could starve your web server of RAM.

By keeping the bot in its own separate container or server, a failure or heavy load on the AI's end will never slow down the site for your human users.

3. Tech Stack Freedom
   Your site and your bot likely need different tools:

The Site: Might be built in Next.js, Go, or Ruby on Rails for fast, scalable web serving.

The Bot: Should almost certainly be written in Python. Python gives you native access to the best data science libraries (Pandas, Scikit-learn, XGBoost) and easy integration with local LLMs via Ollama.

Separating them lets you use the best language for each job.

How It Fits Together (The Blueprint)
Here is how you should structure the ecosystem:

Component Responsibility Tech Stack Example
The Core Site Hosts the UI, user accounts, leaderboards, and the API gateway. Next.js, Node,PostgreSQL

The Data Engine The separate Python app that scrapes stats, runs the ML Python, XGBoost, Pandas
models, and spits out win probabilities.

The Persona Engine Takes the data engine's math and uses a local LLM to Ollama (running Llama 3
generate the arrogant, clinical trash talk. or Mistral)

The Workflow:

1. The Core Site's database updates with the new weekly schedule.

2. The Bot (via a cron job) queries the Site API: GET /api/schedule.

3. The Bot passes the schedule to the Data Engine to get the mathematical picks.

4. The Bot passes those picks and some contextual stats to the Persona Engine (Ollama) with a prompt: "Write a clinical, arrogant forum post announcing these picks."

5. The Bot sends the final payload back to the site: POST /api/predictions and POST /api/comments.

### API Endpoints

To enable a completely separate, decoupled @TheRival application to interact seamlessly with your core website, your platform needs to expose a secure, dedicated set of API endpoints. These endpoints allow the bot to read game data, authenticate itself, submit its predictions before the deadline, and post comments on forums or live game threads.

By treating the bot as an API consumer, you guarantee that it follows the exact same platform rules, constraints, and timestamps as human users.

Required API Endpoints
The endpoints can be categorized into three main domains: Identity, Contest Interaction, and Social Engagement.

1. Authentication & Security
   The bot must authenticate securely to prove its identity and prevent malicious actors from spoofing its account or its trash-talk commentary.

POST /api/v1/auth/bot-login

    Purpose: Authenticates the bot service using a secure API Key or OAuth2 client credentials.

    Returns: A short-lived JWT (JSON Web Token) that the bot must include in the header of all subsequent requests (Authorization: Bearer <token>).

2. Contest & Data Sync
   These endpoints allow the bot to see what games are coming up and submit its official entries.

GET /api/v1/contest/active-slates

    Purpose: The bot calls this to fetch the current week's active prediction slates, match IDs, current betting lines (spreads/totals), and locking lock times.

POST /api/v1/contest/submissions

    Purpose: The bot submits its official 5 picks for the week.

    Payload Constraints: Must include slate_id, bot_user_id, and an array of selected match_ids with the chosen prediction types. The site validation layer must reject this if the current time is past the slate's lock time.

3. Community & Social Engagement
   This allows the bot to post its automated analysis and interactive engagement directly into your site's social spaces.

POST /api/v1/forum/topics

    Purpose: Used by the bot to publish its weekly "Benchmark Drop" thread or post-game analysis summaries.

POST /api/v1/forum/comments

    Purpose: Allows the bot to reply directly to a specific user's comment thread or chime into a live game feed with analytical commentary.

Interactive API Flow & Payload Explorer
To visualize how these systems interact in real time, explore the interactive architecture map below. You can select different operations to see how the data travels between your Core Site, the Bot's Data Engine, and the Ollama Persona Engine, along with sample JSON payloads.

API Flow & Payload Explorer:

See [API-FLOW-PAYLOAD.md](API-FLOW-PAYLOAD.md) for a text-based version of the flow diagram and payload examples.

Endpoint Status
/v1/auth/login 200 OK

Process Selection < Fetch Active Slates >

Refer to [API-FLOW-PAYLOAD.md](API-FLOW-PAYLOAD.md)

#### Validation Rules

#### Implementatoionm

Yes. For this design, the Rival should live side-by-side with HaynesWorld as a separate repo/folder, not nested inside the app.

That gives you the clean separation you want:

Independent deploys and rollbacks.
Separate dependency set and runtime environment.
Cleaner security boundary, so the bot only talks to HaynesWorld through the API.
Easier future scaling if you move the AI pieces to stronger hardware or a different host.
The main app should keep only the API contract, auth, and any shared schema/docs it needs. The Rival repo should own the worker, Ollama integration, persona logic, and its own config/secrets.

If you want, I can move the scaffold out to a sibling folder layout next and leave HaynesWorld with just the API-facing pieces.

Done. The Rival scaffold now lives in a separate sibling folder beside HaynesWorld, so it can be developed and deployed independently. I also validated the new Python package with a compile check, and it passed.
