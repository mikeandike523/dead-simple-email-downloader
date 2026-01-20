# DSED Email Download Specification

> **Dead Simple Email Downloader (DSED)** Condensed, implementation-oriented specification for downloading and exporting email data via Microsoft Graph JSON APIs.

---

## 1. Core principles

1. **Never fetch raw MIME** (`/messages/{id}/$value`). Use Microsoft Graph JSON endpoints and attachment endpoints only.
2. **Preserve metadata, not protocol fidelity.** Export what Graph exposes; do not attempt byte-identical reconstruction of emails.
3. **Messages are the unit of truth.** Conversations exist only for grouping, ordering, and progress reporting.
4. **Disk output is for humans.** Structure must be predictable, readable, and inspectable.
5. **Never infer attachments from body text.** Attachments are authoritative only via the Graph attachment model.

---

## 2. Shortcodes (path-safe IDs)

Long Graph IDs must never be used directly in filesystem paths. DSED therefore uses **shortcodes**:

- **Definition:** `shortcode = "__" + sha256(id).hexdigest()[:N] + "__"` (hex only).
- **Length growth:** start with 8 hex chars, then 12, 16, 20, ... until **all** shortcodes in a set are unique.
- **Uniqueness scope (must be enforced):**
  - all folders (global set)
  - conversations within a folder
  - messages within a conversation
  - attachments within a message (including inline and item attachments)
- **Reversibility:** every shortcode must be reversible to its original Graph ID via persisted mappings.

Mapping requirements:

- Folder shortcodes are stored in `.dsed/index/shortcodes/folders.json`, and each folder node in `.dsed/index/folders.json` includes a `shortcode`.
- Conversation indices embed `conversationShortcodes`, `messageShortcodes`, and per-message `shortcode`.
- Each message folder contains `attachment_shortcodes.json` plus `files_map.json` entries with `attachmentShortcode`.

All directory names and attachment filenames must use shortcodes.

---

## 3. Input model (prebuilt index)

DSED assumes a prebuilt, authoritative conversation index per folder:

```
.dsed/index/conversations-organized/__<folder_shortcode>__.json
```

Conceptual structure:

```json
{
  "folderId": "...",
  "folderShortcode": "__abcd1234__",
  "conversationShortcodes": { "__c0ffee01__": "..." },
  "conversations": [
    {
      "conversationId": "...",
      "conversationShortcode": "__c0ffee01__",
      "messageShortcodes": { "__deadbeef__": "..." },
      "messages": [
        { "id": "...", "shortcode": "__deadbeef__" }
      ]
    }
  ]
}
```

Rules:

- This index is authoritative for **conversation grouping** and **message order**.
- Metadata contained in the index is **not reused** during download.
- All message data is fetched fresh from Graph during export.

---

## 4. Cache and export layout (authoritative)

For each folder:

```
.dsed/caches/__<folder_shortcode>__/
  __<conversation_shortcode>__/
    __<message_shortcode>__/
      message.json
      attachment_shortcodes.json
      files_map.json
      body.html | body.txt
      uniqueBody.html | uniqueBody.txt
      body_noParse.html          (only if rewritten)
      uniqueBody_noParse.html    (only if rewritten)
      attachments/
        files/
        links/
        items/
      inline/
```

Rules:

- All directories are created deterministically, even if empty.
- Shortcodes are always used for directory names.
- Filenames are **not authoritative**; mappings are.

---

## 5. Filename sanitization and mapping (critical rule)

### 5.1 Sanitized filenames

When saving any binary file (attachments or inline):

- The **original filename from Graph** is preserved in metadata.
- A **sanitized filename** is generated for disk storage.
- **The sanitized filename MUST include the file extension**, which is considered part of the sanitization process.

Examples:

- Original: `Quarterly Report (Final).PDF`
- Sanitized: `quarterly_report_final.pdf`

The goal is that files remain:

- readable in file explorers
- openable by common tools
- stable across platforms

### 5.2 `files_map.json` (mandatory)

Every message directory contains a `files_map.json` file. This file is the **authoritative record** linking Graph objects to on-disk files.

Every downloaded attachment or inline blob MUST have an entry.

Each entry records:

- `attachmentId`
- `attachmentShortcode`
- attachment type (`fileAttachment`, `referenceAttachment`, `itemAttachment`)
- `isInline` (boolean)
- `originalName` (as provided by Graph)
- `sanitizedName` (including extension)
- `relativePath` (from the message directory)
- `contentType`
- `size` (if available)
- `contentId` / `contentLocation` (if applicable)
- optional: content hash

This guarantees:

- sanitization rules can change across versions
- duplicate names are safe
- provenance is never lost

---

## 6. Download algorithm (per folder)

### 6.1 Iterate conversations

For each conversation in the index:

- Create `.dsed/caches/__<folder_shortcode>__/__<conversation_shortcode>__/`

### 6.2 Iterate messages (ordered)

For each message ID:

- Create message directory
- Create standard subfolders (`attachments/`, `inline/`)
- Initialize empty `files_map.json`

---

## 7. Message retrieval and metadata

### 7.1 Fetch message

- Fetch the message from Graph fresh.
- Store verbatim metadata in `message.json`.

Recommended fields include:

- `id`, `conversationId`
- `subject`
- `from`, `to`, `cc`, `bcc`
- `sentDateTime`, `receivedDateTime`
- `internetMessageId` (if available)
- `hasAttachments`
- `body` and `uniqueBody` contentType only (no content payload)

Do not store `body.content` or `uniqueBody.content` in `message.json`; the body data lives in `body.html` / `body.txt` files.

### 7.2 Canonical content rule

- `body` is canonical and intended for human inspection.
- `uniqueBody` is heuristic and provided for convenience only.

---

## 8. Body export rules

### 8.1 Primary body

- Use the server-default representation (no `Prefer` header).
- If `contentType == "html"` → `body.html`
- If `contentType == "text"` → `body.txt`
- If missing → record null in JSON and omit the file (or create empty; be consistent).

### 8.2 Unique body

- Export `uniqueBody` in the same representation:
  - `uniqueBody.html` or `uniqueBody.txt`

### 8.3 Optional text alternative (future feature)

- Optional second request with:
  ```
  Prefer: outlook.body-content-type="text"
  ```
- Saved as a distinct file (e.g. `body_alt.txt`).
- Must be labeled in metadata as derived or server-generated.

---

## 9. Attachment handling

### 9.1 Attachment discovery

- Fetch `/messages/{id}/attachments`.
- Store full metadata in `attachments.json` or embedded in `message.json`.

### 9.2 Attachment types

#### A) Reference / link attachments

- No binary download.
- Save metadata to:
  ```
  attachments/links/__<attachment_shortcode>__.json
  ```
- Record an entry in `files_map.json` indicating no local file.

#### B) File attachments (non-inline)

- Download bytes via `.../attachments/{id}/$value`.
- Save to:
  ```
  attachments/files/__<attachment_shortcode>__<sanitizedName>
  ```
- Record mapping in `files_map.json`.

#### C) Inline file attachments

- Download bytes like normal file attachments.
- Save to:
  ```
  inline/__<attachment_shortcode>__<sanitizedName>
  ```
- Record mapping, including `contentId` / `contentLocation`.

#### D) Item attachments (recursive)

- Create:
  ```
  attachments/items/__<attachment_shortcode>__/
  ```
- Export embedded items:
  - Messages → nested message export using the same rules
  - Events → JSON + `.ics`
  - Contacts → JSON + optional `.vcf`
- Recurse for nested attachments.

---

## 10. Inline attachment rewrite (HTML only)

### 10.1 When to rewrite

- Body is HTML **and**
- At least one inline attachment has a usable `contentId` (or `contentLocation`).

### 10.2 Rewrite procedure

1. Save original HTML to `body_noParse.html`.
2. Build a CID → local path map using `files_map.json`.
3. Rewrite only matching `cid:` references.
4. Save rewritten HTML as `body.html`.

### 10.3 Text bodies

- Inline rendering is not meaningful for plain text.
- No rewrite required (optional placeholder replacement only).

---

## 11. Consistency rules (non-negotiable)

- Always produce the same directory skeleton.
- Always record metadata and mappings.
- Never merge attachments across messages.
- Never deduce attachment presence from prose.
- IDs are authoritative; filenames are convenience.

---

## 12. Progress reporting (CLI)

DSED provides folder-scoped progress reporting using a single `tqdm` progress bar per folder.

### 12.1 Progress unit definition

For a given folder, the progress bar total (`total_items`) is computed as:

- `total_items = sum(len(conversation.messages) for conversation in folder_index)`

Where `folder_index` is loaded from:

```
.dsed/index/conversations-organized/__<folder_shortcode>__.json
```

Notes:

- The progress bar counts **top-level messages only**.
- **Recursive walking for item attachments is intentionally excluded** from the item count, because recursion occurs later during attachment download.
- Attachment download work (including recursion) may therefore cause uneven time per tick; this is acceptable for the current UX goals.

### 12.2 Labeling and folder positioning

The progress bar label must be:

- `Processing folder <folder name> (folder {}/{}).`

Where:

- `<folder name>` is the user-facing folder display name.
- `{}/{} ` indicates the folder position in the overall folder processing run (e.g., `folder 2/7`).

Implementation detail:

- The exact source of folder display name and folder ordering may differ depending on the codebase structure; the implementing agent should inspect the existing index and folder enumeration logic to locate the appropriate fields.

### 12.3 Progress update timing

Increment the progress bar by 1 for each top-level message after the message’s export step completes for that folder scope (i.e., after message metadata/body export and top-level attachment handling initiation, according to the project’s existing pipeline stages).

---

## 13. Design stance (summary)

> **Messages are independent documents.** **Conversations are organizational overlays.** **Filenames are UI; mappings are truth.**

This specification favors correctness, debuggability, and long-term stability over protocol completeness or storage minimization.
