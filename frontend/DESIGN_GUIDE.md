# Southview OCR - Visual Design Guide

## Color System

### Primary Colors
- **Indigo (#4F46E5)** - Primary actions, branding, system elements
- **Blue (#3B82F6)** - Secondary actions, informational elements
- **Red (#DC2626)** - Flagged cards (<70% confidence), errors, critical actions
- **Yellow (#F59E0B)** - Pending review (70-84% confidence), warnings
- **Green (#10B981)** - Auto-approved (≥85% confidence), success states
- **Emerald (#059669)** - Approved/corrected records, final success

### Neutral Colors
- **Gray-50 to Gray-900** - Text, backgrounds, borders
- **White (#FFFFFF)** - Card backgrounds, primary surface

## Component Patterns

### Metric Cards
```
┌─────────────────────────────┐
│ [Icon]  Label               │
│         XXX (large number)  │
│         Sublabel            │
└─────────────────────────────┘
```
- Background: Colored with 50 opacity (e.g., bg-red-50)
- Border: Colored with 200 opacity (e.g., border-red-200)
- Text: Colored with 900 opacity (e.g., text-red-900)
- Icon: White background with 50% opacity, colored icon

### Status Chips
```
┌──────────────┐
│  ● Completed │  (Green)
└──────────────┘

┌──────────────┐
│  ● Running   │  (Yellow)
└──────────────┘

┌──────────────┐
│  ● Failed    │  (Red)
└──────────────┘
```
- Small: px-2 py-0.5 text-xs
- Medium: px-3 py-1 text-sm
- Rounded-full with colored background + border

### Confidence Badge
```
┌─────┐
│ 87% │  Green border (≥85%)
└─────┘

┌─────┐
│ 74% │  Yellow border (70-84%)
└─────┘

┌─────┐
│ 52% │  Red border (<70%)
└─────┘
```
- Score percentage in bold
- Optional band label: "Auto-approved (≥85%)"

### Tables
```
┌──────────────────────────────────────────────────────┐
│ HEADER 1        HEADER 2        HEADER 3   ACTIONS   │ (Gray-50 bg)
├──────────────────────────────────────────────────────┤
│ Row data        Row data        [Chip]     Link →    │ (Hover: Gray-50)
│ Row data        Row data        [Chip]     Link →    │
│ Row data        Row data        [Chip]     Link →    │
└──────────────────────────────────────────────────────┘
```
- Header: bg-gray-50, uppercase text-xs font-semibold
- Rows: border-b border-gray-100, hover:bg-gray-50
- White background, rounded-xl with border

### Drawers (Side Panels)
```
┌─────────────────────┐
│ Header        [X]   │ (Sticky)
├─────────────────────┤
│                     │
│ Content             │
│ sections            │
│                     │
│ Actions             │
└─────────────────────┘
```
- Fixed inset-y-0 right-0
- Width: 500px
- z-index: 50
- Backdrop: fixed inset-0 bg-black/20 z-40

### Accordions
```
▼ Section Title
  ┌─────────────────┐
  │ Content         │
  │ visible         │
  └─────────────────┘

▶ Section Title (collapsed)
```
- Radix UI Accordion
- ChevronDown icon rotates on open
- Border-bottom between sections

## Layout Structure

### Page Layout
```
┌──────────────────────────────────────────────────────┐
│ [Pipeline Stepper] (if applicable)                   │
├────────┬─────────────────────────────────────────────┤
│        │ p-8 max-w-7xl mx-auto                       │
│        │                                              │
│        │ [Page Header]                                │
│ Side   │ [Page Content]                               │
│ bar    │   - Cards                                    │
│ (64)   │   - Tables                                   │
│        │   - Forms                                    │
│        │                                              │
│        │                                              │
└────────┴─────────────────────────────────────────────┘
```

### Review Page Layout (Special)
```
┌──────────────────────────────────────────────────────┐
│ [Action Header Bar]                                  │
├──────────────────────┬───────────────────────────────┤
│ Image Viewer         │ Form (Accordion Sections)     │
│ (50% width)          │ (50% width)                   │
│                      │                               │
│ [Zoom controls]      │ ▼ Header Info                 │
│                      │ ▼ Ownership                   │
│ [Image]              │ ▼ Dates                       │
│                      │ ▼ Location                    │
│                      │ ▼ Details                     │
│ [Thumbnails]         │ ▶ Raw OCR Data                │
│                      │ [Keyboard Hints]              │
└──────────────────────┴───────────────────────────────┘
```

## Typography Scale

### Headings
- **H1:** text-3xl font-bold (36px) - Page titles
- **H2:** text-xl font-semibold (20px) - Section titles
- **H3:** text-lg font-semibold (18px) - Subsection titles

### Body Text
- **Regular:** text-base (16px)
- **Small:** text-sm (14px) - Table cells, descriptions
- **Extra Small:** text-xs (12px) - Labels, hints, metadata

### Font Weights
- **Bold:** font-bold (700) - Headlines, important numbers
- **Semibold:** font-semibold (600) - Section headers, button text
- **Medium:** font-medium (500) - Navigation items, form labels
- **Regular:** (400) - Body text

## Spacing System

### Padding
- **Page content:** p-8 (32px)
- **Cards:** p-6 (24px)
- **Compact cards:** p-4 (16px)
- **Table cells:** px-6 py-4 (24px horizontal, 16px vertical)
- **Buttons:** px-4 py-2 (medium), px-6 py-3 (large)

### Margins
- **Section spacing:** mb-8 (32px)
- **Element spacing:** mb-4, mb-6 (16px, 24px)
- **Tight spacing:** mb-2 (8px)

### Gaps
- **Grid gaps:** gap-4, gap-6 (16px, 24px)
- **Flex gaps:** gap-2, gap-3 (8px, 12px)

## Border & Radius

### Border Widths
- **Standard:** border (1px)
- **Thick:** border-2 (2px) - Focus states

### Border Radius
- **Cards:** rounded-xl (12px)
- **Buttons/Inputs:** rounded-lg (8px)
- **Chips:** rounded-full
- **Small elements:** rounded (4px)

## Interactive States

### Buttons
- **Default:** bg-indigo-600 text-white
- **Hover:** hover:bg-indigo-700
- **Disabled:** disabled:opacity-50 disabled:cursor-not-allowed
- **Focus:** focus:outline-none focus:ring-2 focus:ring-indigo-500

### Links
- **Default:** text-indigo-600
- **Hover:** hover:text-indigo-800
- **Underline on hover:** hover:underline

### Table Rows
- **Default:** border-b border-gray-100
- **Hover:** hover:bg-gray-50
- **Clickable:** cursor-pointer

### Form Inputs
- **Default:** border border-gray-300
- **Focus:** focus:outline-none focus:ring-2 focus:ring-indigo-500
- **Error:** border-red-300 bg-red-50

## Icon Usage

### Icon Sizes
- **Small:** w-4 h-4 (16px) - Inline with text
- **Medium:** w-5 h-5 (20px) - Buttons, navigation
- **Large:** w-6 h-6, w-8 h-8 (24px, 32px) - Headers, feature icons

### Common Icons (Lucide React)
- **Navigation:** LayoutDashboard, Video, Cog, ListChecks, Search, FileDown, Settings
- **Actions:** Upload, Play, Eye, Save, CheckCircle, Flag, Edit3, ArrowRight
- **UI:** ChevronDown, ChevronUp, ChevronLeft, ChevronRight, X, Filter
- **Media:** ZoomIn, ZoomOut, RotateCw
- **Status:** AlertTriangle, AlertCircle, Info, Database

## Animation & Transitions

### Smooth Transitions
- **Color changes:** transition-colors
- **All properties:** transition-all
- **Transforms:** transition-transform duration-200
- **Shadow:** hover:shadow-md transition-shadow

### Transform Effects
- **Image zoom:** `transform: scale(${zoom})`
- **Image rotate:** `transform: rotate(${rotation}deg)`
- **Accordion chevron:** `group-data-[state=open]:rotate-180`

## Responsive Breakpoints

### Desktop-First Approach
- **Desktop:** 1280px+ (default)
- **Tablet:** 768px-1279px (sidebar may collapse)
- **Mobile:** <768px (tables scroll, review page stacks)

### Responsive Patterns
- **Tables:** Horizontal scroll on narrow screens
- **Grids:** grid-cols-3 → grid-cols-2 → grid-cols-1
- **Split layouts:** Two columns → Stack vertically
- **Sidebar:** Fixed → Collapsible drawer

## Accessibility Considerations

- **Focus states:** Visible ring on all interactive elements
- **Keyboard navigation:** Tab order follows visual flow
- **Semantic HTML:** Proper heading hierarchy, button vs. link
- **ARIA labels:** Screen reader support on icons-only buttons
- **Color contrast:** WCAG AA compliant text colors
- **Alt text:** Descriptive text for all images

## Empty & Error States

### Empty State Pattern
```
┌─────────────────────────────┐
│                             │
│      [Icon]                 │
│   No items found            │
│   Description text          │
│   [Action Button]           │
│                             │
└─────────────────────────────┘
```
- Centered content
- Gray icon (w-8 h-8)
- Clear message and optional CTA

### Error State Pattern
```
┌─────────────────────────────┐
│ ⚠ Error Message             │
│   Additional details...     │
│   [Retry Button]            │
└─────────────────────────────┘
```
- Red background (bg-red-50)
- Red border (border-red-200)
- Alert icon
- Clear error message

## Loading States

### Progress Bars
```
┌──────────────────────────┐
│ ████████░░░░░░░░░░ 45%   │
└──────────────────────────┘
```
- Container: bg-gray-200 h-2 rounded-full
- Fill: bg-indigo-600 rounded-full
- Percentage text: text-sm font-medium

### Inline Spinners
- Small circular spinner
- Indigo color
- Used for async button actions

## Consistency Checklist

✅ All metric cards use same pattern (icon + number + label)
✅ All tables have gray-50 header + hover states
✅ All status chips use consistent sizing
✅ All drawers slide from right, 500px width
✅ All accordions use ChevronDown icon
✅ All page headers have title + description
✅ All action buttons show keyboard hints in review context
✅ All confidence badges color-coded by band
✅ All navigation items use consistent padding and active state
✅ All forms use consistent input styling
