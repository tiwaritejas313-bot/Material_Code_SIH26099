// Minimal outline icons, stroke=currentColor so they inherit the nav item's
// text color automatically (active/inactive/hover all handled by CSS alone).
const base = { width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };

export const IconGrid = () => (
  <svg {...base}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>
);

export const IconChecklist = () => (
  <svg {...base}><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" /></svg>
);

export const IconLink = () => (
  <svg {...base}><path d="M9 12h6" /><path d="M10 6H6a4 4 0 0 0 0 8h1" /><path d="M14 18h4a4 4 0 0 0 0-8h-1" /></svg>
);

export const IconChart = () => (
  <svg {...base}><path d="M4 20V10M12 20V4M20 20v-7" /></svg>
);

export const IconSearch = () => (
  <svg {...base}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
);

export const IconLogout = () => (
  <svg {...base}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></svg>
);
