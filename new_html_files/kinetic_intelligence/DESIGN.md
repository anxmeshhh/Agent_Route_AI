# Design System Specification

## 1. Overview & Creative North Star
**The Creative North Star: "The Kinetic Intelligence"**

This design system is built to bridge the gap between complex logistical data and hyper-intelligent AI reasoning. It moves beyond the static "dashboard" trope, opting instead for a **Kinetic Intelligence** aesthetic—where information feels like it is being actively processed in real-time. 

We break the "standard SaaS template" by embracing **Tonal Deep-Diving**. Rather than using rigid boxes to separate ideas, we use light, depth, and atmospheric blur to guide the eye. The layout should feel like a high-end command deck: intentional asymmetry, high-contrast data visualization, and "floating" glass modules that prioritize clarity over containment.

---

## 2. Colors & Surface Logic

### The "No-Line" Rule
Traditional 1px borders are prohibited for sectioning. Structural definition must be achieved through **Value Shifting**. To separate a sidebar from a main feed, use a shift from `surface` (#0D0E17) to `surface-container-low` (#12131D). Boundaries are felt, not seen.

### Surface Hierarchy (Dark Mode Focus)
| Token | Hex | Role |
| :--- | :--- | :--- |
| `background` | #0D0E17 | The infinite void. Base layer. |
| `surface-container-low` | #12131D | Primary navigational regions (Sidebars). |
| `surface-container` | #181924 | Standard content cards. |
| `surface-container-high`| #1D1F2B | Nested interactive elements. |
| `surface-bright` | #2A2B3A | Overlays and high-focus modals. |

### Glass & Gradients
To evoke a premium "AI-Native" feel, floating elements (tooltips, active route nodes) must use:
- **Glassmorphism:** `background: rgba(24, 25, 36, 0.7); backdrop-filter: blur(20px);`
- **Primary Gradient:** `#00D9FF` → `#7C3AED` (Used for active AI paths and primary CTAs).
- **Secondary Glow:** Subtle `primary_dim` (#8A4CFC) shadows to indicate "system activity."

---

## 3. Typography
We utilize a modular scale to ensure that dense logistical data remains legible while maintaining an editorial "premium" feel.

- **Headings (Inter/Geist):** Semi-bold (600) to Bold (700). High tracking (-0.02em) for a compact, authoritative look.
- **Body (Inter):** Regular weight. Used for reasoning logs and descriptions.
- **Data (JetBrains Mono):** Reserved for coordinates, ETAs, and risk scores to provide a "technical" hardware-interface feel.

| Level | Size | Token | Usage |
| :--- | :--- | :--- | :--- |
| Display LG | 3.5rem | `display-lg` | Hero marketing/Landing. |
| Headline SM | 1.5rem | `headline-sm` | Major module headers. |
| Title SM | 1.0rem | `title-sm` | Card titles. |
| Body MD | 0.875rem | `body-md` | Default UI text. |
| Label SM | 0.6875rem | `label-sm` | Metadata and status tags. |

---

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved by "stacking" container tiers. A `surface-container-highest` card should sit atop a `surface-container-low` background. This creates a natural, soft lift.

### Ambient Shadows
Avoid black shadows. Use tinted shadows for a "glow" effect:
- **Style:** `box-shadow: 0 8px 32px rgba(189, 157, 255, 0.08);` (Using the `surface_tint` color).
- **The Ghost Border:** If accessibility requires a border, use `outline-variant` (#474752) at **15% opacity**.

---

## 5. Components

### Primary Buttons (The "Core Action")
- **Style:** Animated gradient background (`primary` to `primary_dim`).
- **Rounding:** 8px (via `DEFAULT` roundedness scale).
- **Interaction:** On hover, increase the `backdrop-filter: brightness(1.2)` and add a 4px `primary` outer glow.

### Intelligence Chips (Status Tags)
- **Selection Chips:** Use `secondary_container` (#00687B) with `on_secondary` (#004755) text.
- **Critical Risk:** Use `error_container` (#A70138) with `error` (#FF6E84) text. Forbid solid fills; use 20% opacity fills with high-saturation text for a "glass tag" look.

### Input Fields
- **Background:** `surface_container_highest` (#242532).
- **Border:** None. Use a bottom-only 2px accent line that activates on focus using the `secondary` (#00D9FF) token.

### Data Lists
- **Rule:** Forbid divider lines. 
- **Solution:** Use 12px vertical spacing between items. On hover, the entire list item should transition to `surface_bright` (#2A2B3A) with a `200ms ease`.

### Logistics Specific: The Reasoning Module
- A vertical "thread" component using the `outline` (#757480) color at 20% opacity to connect AI decision nodes.
- Use `JetBrains Mono` for the timestamp and `Inter` for the reasoning text.

---

## 6. Do's and Don'ts

### Do
- **DO** use asymmetry. Place primary data (Risk Scores) off-center to create a dynamic, modern feel.
- **DO** use "Breathing Room." High-density data needs 16px to 24px of internal padding.
- **DO** use color for intent. `tertiary` (#FFB148) is for warnings only; do not use it for aesthetic accents.

### Don't
- **DON'T** use 100% opaque, high-contrast borders. It breaks the "Kinetic Intelligence" immersion.
- **DON'T** use pure black (#000000) backgrounds for content panels; keep them for the "lowest" container depth only.
- **DON'T** mix rounded corners. Stick to the scale: 12px for cards, 8px for inputs/buttons, 16px for major layout regions.

---