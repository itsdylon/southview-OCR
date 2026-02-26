# Southview OCR - Index Card Digitization System

A clean, workflow-first web application for digitizing historical index cards from iPhone video into structured, searchable, confidence-scored records with a manual review workflow.

## Overview

Southview OCR transforms raw video footage of historical burial index cards into structured, searchable database records through an automated pipeline with intelligent confidence-based review routing.

## Pipeline Architecture

```
Video Upload → Frame Extraction → OCR + Scoring → Database → Review Workflow → Export & Backup
```

### Confidence-Based Routing

- **≥85% confidence** → Auto-approved (no manual review needed)
- **70-84% confidence** → Pending review (routine verification)
- **<70% confidence** → Flagged (priority review required)

## Core Features

### 1. **Overview Dashboard**
- Pipeline status at a glance (Videos Processing, Jobs Running, Cards by confidence band)
- Intelligent "Next best action" banner that deep-links to most urgent task
- Recent jobs table with progress tracking

### 2. **Videos Management**
- Upload and track video files
- View processing status and card counts
- Start full pipeline or individual jobs (frame extraction, OCR)
- Video detail page shows linked jobs and extracted cards

### 3. **Jobs Monitoring**
- Real-time job progress tracking
- Filter by status (queued/running/completed/failed) and type
- Side drawer for detailed logs and error inspection
- Retry controls for failed jobs

### 4. **Review Queue** (Primary Workflow Hub)
- Smart prioritization: flagged cards first, then pending, then auto-approved
- Filter by video, confidence band, and review status
- Quick stats showing cards by confidence level
- One-click navigation to individual card review

### 5. **Review & Verify** (Two-Column Layout)
- **Left:** Image viewer with zoom, rotate, and contrast controls
- **Right:** Structured form with accordion sections:
  - Header (deceased name, address)
  - Ownership (owner, relation, phone)
  - Dates (death, burial)
  - Location/Description
  - Additional Details (sex, age, grave type, undertaker, etc.)
- Confidence score prominently displayed with band label
- Raw OCR text and JSON preserved for audit trail
- Keyboard shortcuts (A=Approve, C=Corrected, F=Flag, S=Save, J/K=Navigate)

### 6. **Search**
- Name-first search with real-time results
- Advanced filters: date range, sex, undertaker, location keywords
- Side panel shows full record details with image
- Direct link to full review page

### 7. **Export & Backup**
- Export approved/corrected records as CSV or JSON
- Filter by video, review status, confidence band
- Manual database backup with history tracking
- Backup restoration preview

### 8. **Settings**
- **Confidence Thresholds:** Visual sliders for auto-approve (default 85%) and pending review (default 70%)
- **OCR Engine:** Choose from Tesseract, Google Cloud Vision, Azure
- **Processing Options:** Image preprocessing, structured field extraction, handwriting detection
- **Advanced Settings:** Frame extraction rate, duplicate detection threshold, debug logging

## Technology Stack

- **Frontend:** React 18 + TypeScript + Vite
- **Routing:** React Router 7 (Data mode)
- **Styling:** Tailwind CSS v4
- **UI Components:** Radix UI (Accordion for collapsible sections)
- **Icons:** Lucide React

## Information Architecture

### Navigation (Left Sidebar)
1. Overview
2. Videos
3. Jobs
4. Review Queue ⭐ (primary workflow)
5. Search
6. Export & Backup
7. Settings

### Pipeline Stepper (Top Bar)
Shows current stage with item counts:
- Upload
- Extract (frame extraction)
- OCR
- Review
- Export

## Data Model

### Core Entities

**Video**
- `id`, `filename`, `status` (uploaded/processing/completed/failed)
- `uploadedAt`, `processedAt`, `cardCount`, `frameCount`, `duration`, `fileSize`

**Job**
- `id`, `videoId`, `jobType` (frame_extraction/ocr/full_pipeline)
- `status` (queued/running/completed/failed), `progress` (0-100)
- `createdAt`, `startedAt`, `completedAt`, `errorMessage`

**Card**
- `id`, `videoId`, `imagePath`, `frameNumber`, `sequenceIndex`
- Links to OCRResult

**OCRResult**
- `id`, `cardId`, `reviewStatus` (pending/approved/flagged/corrected)
- `confidenceScore` (0.0-1.0), `rawText`, `rawFieldsJson`, `wordConfidences`
- Structured fields: `deceased_name`, `address`, `owner`, `relation`, `phone`, `date_of_death`, `date_of_burial`, `description`, `sex`, `age`, `grave_type`, `grave_fee`, `undertaker`, `board_of_health_no`, `svc_no`

## Design Principles

### Workflow-First
- Clear linear pipeline (Upload → Process → Review → Export)
- Next best action always visible
- Priority-based sorting (flagged → pending → approved)

### Progressive Disclosure
- Advanced filters hidden by default
- Details in side drawers, not cluttered tables
- Collapsible sections for secondary information
- Raw OCR data tucked away for audit purposes

### Tables Over Cards
- Scannable tables with essential columns
- Drill-down drawers for detailed information
- Avoid dense card grids that overwhelm users

### Clear Visual Hierarchy
- Maximum 3-5 key metrics per dashboard
- Generous whitespace and strong typography
- Consistent color coding:
  - Indigo: Primary actions, system branding
  - Red: Flagged/errors (<70% confidence)
  - Yellow: Pending review (70-84%)
  - Green: Auto-approved/success (≥85%)

## Sample Data

The application includes comprehensive mock data:
- **3 videos** in various states (completed, processing, uploaded)
- **6 jobs** showing different job types and statuses
- **6+ cards** spanning all confidence bands and review statuses
- Realistic OCR results with varied data quality

## API Endpoints (Assumed)

```
POST   /api/videos/upload
GET    /api/videos
GET    /api/videos/{id}
POST   /api/jobs/{video_id}/start
GET    /api/jobs/{id}
GET    /api/cards  (filterable)
GET    /api/cards/{id}
PUT    /api/cards/{id}/review
GET    /api/export
POST   /api/backup
```

## Keyboard Shortcuts (Review Page)

- **A** - Approve record
- **C** - Mark as corrected
- **F** - Flag for priority review
- **S** - Save changes
- **J** - Previous card
- **K** - Next card

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## File Structure

```
src/app/
├── pages/
│   ├── ocr-overview-page.tsx         # Dashboard with pipeline metrics
│   ├── videos-page.tsx                # Videos list
│   ├── video-detail-page.tsx          # Video detail with jobs/cards
│   ├── ocr-jobs-page.tsx              # Jobs monitoring with drawer
│   ├── ocr-review-queue-page.tsx      # Review queue (primary workflow)
│   ├── ocr-review-verify-page.tsx     # Card review (two-column)
│   ├── ocr-search-page.tsx            # Search with filters
│   ├── export-backup-page.tsx         # Export & backup management
│   └── ocr-settings-page.tsx          # System configuration
├── components/
│   ├── sidebar.tsx                    # Main navigation
│   ├── pipeline-stepper.tsx           # Workflow progress indicator
│   ├── confidence-badge.tsx           # Confidence score display
│   ├── status-chip.tsx                # Status pills
│   ├── quality-alert-card.tsx         # Alert cards
│   └── empty-state.tsx                # Empty state placeholder
├── layouts/
│   └── dashboard-layout.tsx           # Main layout wrapper
├── types/
│   └── ocr.ts                         # TypeScript type definitions
├── data/
│   └── ocrMockData.ts                 # Sample data for demo
├── routes.ts                          # Route configuration
└── App.tsx                            # Root component
```

## Key Components

### ConfidenceBadge
Displays confidence score with color-coded band label (Auto-approved/Pending/Flagged)

### PipelineStepper
4-stage progress indicator (Upload → Extract → OCR → Review → Export)

### StatusChip
Colored pills for video/job/review statuses

### Sidebar
Fixed left navigation with all main sections

## Responsive Design

- **Desktop-first:** Optimized for 1280px+ workflow screens
- **Tablet-compatible:** Sidebar collapses, tables scroll horizontally
- **Review page:** Stacks vertically on narrow screens

## States & Feedback

- **Loading:** Inline spinners, progress bars
- **Errors:** Alert banners, error messages in job drawer
- **Empty:** Placeholder messages with call-to-action
- **Success:** Toast notifications (assumed), status chips

## Future Enhancements

- Real-time job progress via WebSocket
- Batch approval/correction actions
- Export scheduling and automation
- User audit trail and version history
- Multi-language OCR support
- Handwriting-specific OCR models

---

Built with ❤️ for Southview Cemetery digitization project
