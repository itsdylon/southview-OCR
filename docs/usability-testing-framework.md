# Southview OCR — Usability Testing Framework

## Project Summary

**Southview OCR** is a cemetery index card digitization app. It processes iPhone video recordings of historical burial index cards, extracts text via OCR, and provides a human review workflow with confidence scoring. The frontend is a 9-page React prototype (Figma Make export) with mock data.

---

## 1) Draft Link

You need to deploy or host the prototype so testers can access it. Options:

| Method | Command | Result |
|---|---|---|
| **Local dev server** | `npm run dev` (or `pnpm dev`) | `http://localhost:5173` — tester must be on your machine or same network |
| **Vercel/Netlify** | Connect the GitHub repo | Public URL you can share (recommended for the report) |
| **GitHub Pages** | `npm run build` then deploy `dist/` | Free public hosting |

Since the backend isn't connected yet, the frontend runs entirely on **mock data** — which is fine for UI/UX testing.

---

## 2) What Is User-Facing and Needs to Be Tested

The app has **9 pages** across **5 core user journeys**. Here's what testers should evaluate:

### Journey A: Dashboard Orientation (Overview Page `/`)
- **Pipeline stepper** — Is the 4-step workflow (Upload → Process → Review → Publish) understandable?
- **Next Best Action banner** — Does the tester understand what they should do next?
- **6 metric cards** — Are the labels (Videos Processing, Jobs Running, Cards Flagged, Pending Review, Auto-approved, Approved/Corrected) clear?
- **Recent Jobs table** — Can they interpret status, progress bars?

### Journey B: Video Upload & Processing (`/videos`, `/videos/:id`, `/jobs`)
- Can they find the **Upload Video** button?
- Do they understand video status chips (uploaded, processing, completed, failed)?
- On the video detail page, is the **Pipeline Stepper** + **Start Full Pipeline** button discoverable?
- On the Jobs page, can they use **filters** (status, job type)?
- Does the **Job Details drawer** (slides in from right) make sense?

### Journey C: Review Workflow (`/review-queue`, `/review/:id`) — THE CRITICAL PATH
- Can they interpret the **flagged cards banner** and know what to do?
- Do they understand **confidence bands** (color-coded: red <70%, yellow 70-84%, green >=85%)?
- Can they navigate the **Review/Verify page** (split-screen: image left, form right)?
- Can they use the **image viewer controls** (zoom, rotate, reset)?
- Do the **15 form fields** and their accordion groupings make sense?
- Are the **action buttons** (Approve, Corrected, Flag, Save) and their meanings clear?
- Do they notice the **keyboard shortcuts** (A, C, F, S, J, K)?
- Can they navigate between cards using **Previous/Next**?

### Journey D: Search & Lookup (`/search`)
- Can they search by deceased name?
- Do they discover the **Advanced Filters** (date range, sex, undertaker, location)?
- Is the **split-view layout** (results list left, detail panel right) intuitive?
- Can they click through to **View Full Record**?

### Journey E: Export & Settings (`/export`, `/settings`)
- Can they figure out how to **export data** (select video, status filter, format)?
- Do they understand the **CSV vs JSON** choice?
- In Settings, do the **confidence threshold sliders** make sense?
- Are the **OCR engine** and **processing options** understandable to a non-technical user?

---

## 3) Testing Method Framework

**Suggested protocol for your 2+ testers:**

### Setup
- Share the prototype link (deployed or screen-share)
- Brief them: *"This app helps digitize old cemetery index cards from video recordings. We'd like you to explore it and complete a few tasks."*
- Don't explain the UI — observe how they navigate on their own

### Task Script (give these one at a time)

| # | Task | What You're Testing |
|---|---|---|
| 1 | "You just opened the app. What do you think this tool does?" | First impression, dashboard clarity |
| 2 | "Find out how many cards need urgent review." | Dashboard metrics readability, flagged count |
| 3 | "Navigate to the review queue and start reviewing a flagged card." | Navigation, review queue understanding |
| 4 | "On the review page, zoom into the card image and correct a field." | Image viewer + form usability |
| 5 | "Approve this card and move to the next one." | Action buttons, navigation flow |
| 6 | "Search for a person named 'Smith' in the database." | Search page discoverability |
| 7 | "Export all approved records as a CSV file." | Export workflow clarity |
| 8 | "Change the auto-approve confidence threshold to 90%." | Settings page, slider interaction |

### Data to Capture
- Time to complete each task (or if they couldn't complete it)
- Where they clicked/looked first (expected vs actual path)
- Verbal reactions ("What does this mean?", "Oh I see", confusion pauses)
- Errors / wrong turns
- Unprompted feedback

---

## 4) Likely Findings to Watch For

Based on analyzing the prototype, here are probable usability issues testers may flag:

| Area | Potential Issue | Why |
|---|---|---|
| **Terminology** | "OCR", "Pipeline", "Confidence Band", "Frame Extraction" are technical jargon | Non-technical users won't know what these mean |
| **Dashboard density** | 6 metric cards + table + stepper + banner is a lot at once | Information overload on first visit |
| **Review page complexity** | 15 form fields + image viewer + actions + shortcuts | Steep learning curve for new reviewers |
| **Confidence colors** | Red/yellow/green may not be sufficient for colorblind users | Accessibility concern |
| **Button clarity** | "Corrected" vs "Approved" distinction isn't obvious | Users may not know which to pick |
| **Navigation** | Sidebar has 7 items — is the hierarchy clear? | "Jobs" vs "Videos" vs "Review Queue" overlap |
| **Empty states** | Many pages use `alert()` placeholders for actions | Testers will notice non-functional buttons |
| **Advanced Filters** | Hidden behind a toggle — testers may not find them | Discoverability issue |
| **Keyboard shortcuts** | Only shown in small text on the review page | Most testers won't notice them |

---

## 5) Action Items Template

After testing, you need **at least 3 specific, concrete changes**. Template:

> **Action 1:** [What you'll change]
> - **Based on finding:** [What the tester said/did]
> - **Specific change:** [Exact UI modification]
> - **Expected improvement:** [How it helps]

### Example actions you might document:

1. **Add plain-language tooltips to jargon terms** — Testers didn't understand "confidence band" or "pipeline". Add hover tooltips like *"Confidence = how sure the computer is about the text it read"*.

2. **Simplify the Review page action buttons** — Testers were confused by the difference between "Approve" and "Corrected". Combine into a single "Approve" button that auto-detects if changes were made.

3. **Add an onboarding walkthrough for first-time users** — Testers didn't know where to start on the dashboard. Add a guided tour highlighting the pipeline steps.

4. **Improve color accessibility on confidence badges** — Add icons (checkmark, warning, alert) alongside colors so colorblind users can distinguish confidence levels.

5. **Make Advanced Filters visible by default on Search page** — Testers didn't discover the hidden filters toggle.

---

## 6) Report Outline

```
# Usability Testing Report — Southview OCR

## Draft Link
[URL to deployed prototype]

## Project Description
Brief: digitization tool for cemetery index cards using OCR

## Usability Testing

### Method
- Number of testers: [2+]
- Tester profiles: [age, tech comfort, relation to project]
- Testing format: [in-person/remote, think-aloud protocol]
- Tasks given: [list the 8 tasks above]
- Duration: [time per session]

### Findings

#### Tester 1: [Name/Alias]
- Task results (completed/struggled/failed)
- What confused them
- What they liked
- Direct quotes
- Navigation issues

#### Tester 2: [Name/Alias]
- [Same structure]

### Common Themes
- [Pattern across testers]

## Action Plan (3+ changes)

### Change 1: [Title]
- Finding: ...
- Change: ...
- Impact: ...

### Change 2: [Title]
...

### Change 3: [Title]
...
```

---

## Summary

- **9 pages** are testable, with the **Review workflow** (`/review-queue` → `/review/:id`) being the most critical path
- The prototype runs on **mock data** so all pages are navigable even without the backend
- Focus testers on **task-based scenarios** (not free exploration) to get structured findings
- The most likely feedback will center on **jargon/terminology**, **review page complexity**, and **discoverability of hidden features**
- Deploy via Vercel/Netlify for a shareable link, or run `pnpm dev` locally for in-person testing
