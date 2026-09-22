# Client source patches — hide Projects, persistent theme toggle, friendlier error text

Written and verified against the actual **v0.8.8-rc2** source (matches your deployed image exactly — confirmed via `package.json` version and CSS variable diff earlier). **Not tested against a real build** — I don't have a way to run your build pipeline. Apply, `docker compose build` (or however your Dockerfile is wired), then check visually before considering this done, especially patch 2.

All three are `client/src/` edits — none touch `gateway/`, `docling_service/`, `ocr_adapter/`, or your `.py` files.

---

## 1. Hide the "Projects" section

**No config flag exists for this** (confirmed — no `interface.projects` key in the schema, no ACL permission gates `ProjectsSection`, it's unconditionally rendered). The safest patch is a one-line guard at the call site, not touching `ProjectsSection.tsx` itself — trivially reversible, no risk of breaking its internal loading/empty/populated states.

**File:** `client/src/components/UnifiedSidebar/ConversationsSection.tsx`

Find:
```tsx
      {!search.query && <ProjectsSection toggleNav={toggleNav} isAuthenticated={isAuthenticated} />}
```

Replace:
```tsx
      {/* Clarisync: Projects hidden for the pilot — no config flag exists for this.
          Restore by changing `false` back to `!search.query`. */}
      {false && <ProjectsSection toggleNav={toggleNav} isAuthenticated={isAuthenticated} />}
```

(Using `false &&` rather than deleting/commenting the line keeps the `ProjectsSection` import "used," so it won't trip an unused-import lint/build error.)

---

## 2. Persistent light/dark toggle in the sidebar

There's already a ready-made, correctly-wired component for this — `ThemeSetting` (in `client/src/components/Nav/Settings/controls.tsx`), which wraps LibreChat's `ThemeSelector` with the right context hook. No need to rebuild that wiring.

**Placement note, honestly flagged:** the sidebar has two panels — a narrow icon-only rail (`ExpandedPanel.tsx`, where the small avatar circle you saw in the corner lives) and the wide panel with actual chat-history text (`ConversationsSection.tsx`). `ThemeSetting` renders a labeled row ("Theme" + a 180px dropdown) — built for a wide panel, and would overflow badly in the narrow rail. So this patch adds it to the **wide** panel, as a footer below the chat list, which is also the better match for "just chat history and a settings section." Check it visually after rebuild — this is the one part of the batch I'd actually want eyes on.

**File:** `client/src/components/UnifiedSidebar/ConversationsSection.tsx`

Add to the imports (anywhere in the existing import block is fine):
```tsx
import { ThemeSetting } from '~/components/Nav/Settings/controls';
```

Find (the component's closing return block):
```tsx
        />
      </div>
    </div>
  );
});

ConversationsSection.displayName = 'ConversationsSection';
```

Replace:
```tsx
        />
      </div>
      <div className="border-t border-border-light px-3 py-2">
        <ThemeSetting />
      </div>
    </div>
  );
});

ConversationsSection.displayName = 'ConversationsSection';
```

---

## 3. Friendlier error text (client half only — see caveat)

**File:** `client/src/components/Messages/Content/Error.tsx`

Find:
```tsx
  const defaultResponse = `Something went wrong. Here's the specific error message we encountered: ${errorMessage}`;
```

Replace:
```tsx
  const defaultResponse = errorMessage;
```

**Caveat, found while tracing this:** the *inner* text your gateway's errors get wrapped in — `"An error occurred while processing the request: <status> ..."` — isn't added client-side at all. It's added **server-side**, in `api/server/controllers/agents/client.js` (via a `getUserFacingRequestError(...)` call), which every endpoint type routes through in this LibreChat version, including custom OpenAI-compatible endpoints like your gateway. This patch removes the outer "Something went wrong..." sentence (the more alarming, debug-looking part) but the inner prefix survives — so you'd go from:

> Something went wrong. Here's the specific error message we encountered: An error occurred while processing the request: 400 'long_35.pdf' has 35 pages...

to:

> An error occurred while processing the request: 400 'long_35.pdf' has 35 pages...

Fully removing that too means patching `api/server/controllers/agents/client.js` (or the shared `getUserFacingRequestError` helper) — a server-side file with a much bigger blast radius (it's the shared error path for every endpoint type, not just custom ones), and I haven't traced its full implementation. I'd want to actually read that function before proposing a change there rather than guess — say the word if you want me to go do that next, separately from this batch.

---

## What ships in the same rebuild, already confirmed as needing one

- These three.
- The "Private · stays on Clarisync servers" header badge (flagged earlier, not drafted).
