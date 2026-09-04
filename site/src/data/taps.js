/** Common 75% thread tap-drill recommendations. Confirm against the tap maker for critical fits. */

export const unc = [
  { screw: '1-64', tap: '#53', inch: 0.0595 },
  { screw: '2-56', tap: '#50', inch: 0.07 },
  { screw: '3-48', tap: '#47', inch: 0.0785 },
  { screw: '4-40', tap: '#43', inch: 0.089 },
  { screw: '5-40', tap: '#38', inch: 0.1015 },
  { screw: '6-32', tap: '#36', inch: 0.1065 },
  { screw: '8-32', tap: '#29', inch: 0.136 },
  { screw: '10-24', tap: '#25', inch: 0.1495 },
  { screw: '12-24', tap: '#16', inch: 0.177 },
  { screw: '1/4-20', tap: '#7', inch: 0.201 },
  { screw: '5/16-18', tap: 'F', inch: 0.257 },
  { screw: '3/8-16', tap: '5/16', inch: 0.3125 },
  { screw: '7/16-14', tap: 'U', inch: 0.368 },
  { screw: '1/2-13', tap: '27/64', inch: 0.4219 },
  { screw: '9/16-12', tap: '31/64', inch: 0.4844 },
  { screw: '5/8-11', tap: '17/32', inch: 0.5312 },
  { screw: '3/4-10', tap: '21/32', inch: 0.6562 },
  { screw: '7/8-9', tap: '49/64', inch: 0.7656 },
  { screw: '1-8', tap: '7/8', inch: 0.875 },
];

export const unf = [
  { screw: '0-80', tap: '#53', inch: 0.0595 },
  { screw: '1-72', tap: '#53', inch: 0.0595 },
  { screw: '2-64', tap: '#50', inch: 0.07 },
  { screw: '3-56', tap: '#45', inch: 0.082 },
  { screw: '4-48', tap: '#42', inch: 0.0935 },
  { screw: '5-44', tap: '#37', inch: 0.104 },
  { screw: '6-40', tap: '#33', inch: 0.113 },
  { screw: '8-36', tap: '#29', inch: 0.136 },
  { screw: '10-32', tap: '#21', inch: 0.159 },
  { screw: '12-28', tap: '#14', inch: 0.182 },
  { screw: '1/4-28', tap: '#3', inch: 0.213 },
  { screw: '5/16-24', tap: 'I', inch: 0.272 },
  { screw: '3/8-24', tap: 'Q', inch: 0.332 },
  { screw: '7/16-20', tap: '25/64', inch: 0.3906 },
  { screw: '1/2-20', tap: '29/64', inch: 0.4531 },
  { screw: '9/16-18', tap: '33/64', inch: 0.5156 },
  { screw: '5/8-18', tap: '37/64', inch: 0.5781 },
  { screw: '3/4-16', tap: '11/16', inch: 0.6875 },
  { screw: '7/8-14', tap: '13/16', inch: 0.8125 },
  { screw: '1-12', tap: '59/64', inch: 0.9219 },
];

export const metricCoarse = [
  { screw: 'M2 × 0.4', tap: '1.6 mm', mm: 1.6 },
  { screw: 'M2.5 × 0.45', tap: '2.05 mm', mm: 2.05 },
  { screw: 'M3 × 0.5', tap: '2.5 mm', mm: 2.5 },
  { screw: 'M3.5 × 0.6', tap: '2.9 mm', mm: 2.9 },
  { screw: 'M4 × 0.7', tap: '3.3 mm', mm: 3.3 },
  { screw: 'M5 × 0.8', tap: '4.2 mm', mm: 4.2 },
  { screw: 'M6 × 1.0', tap: '5.0 mm', mm: 5.0 },
  { screw: 'M8 × 1.25', tap: '6.8 mm', mm: 6.8 },
  { screw: 'M10 × 1.5', tap: '8.5 mm', mm: 8.5 },
  { screw: 'M12 × 1.75', tap: '10.2 mm', mm: 10.2 },
  { screw: 'M14 × 2.0', tap: '12.0 mm', mm: 12.0 },
  { screw: 'M16 × 2.0', tap: '14.0 mm', mm: 14.0 },
  { screw: 'M18 × 2.5', tap: '15.5 mm', mm: 15.5 },
  { screw: 'M20 × 2.5', tap: '17.5 mm', mm: 17.5 },
  { screw: 'M24 × 3.0', tap: '21.0 mm', mm: 21.0 },
];

export const metricFine = [
  { screw: 'M8 × 1.0', tap: '7.0 mm', mm: 7.0 },
  { screw: 'M10 × 1.0', tap: '9.0 mm', mm: 9.0 },
  { screw: 'M10 × 1.25', tap: '8.8 mm', mm: 8.8 },
  { screw: 'M12 × 1.25', tap: '10.8 mm', mm: 10.8 },
  { screw: 'M12 × 1.5', tap: '10.5 mm', mm: 10.5 },
  { screw: 'M14 × 1.5', tap: '12.5 mm', mm: 12.5 },
  { screw: 'M16 × 1.5', tap: '14.5 mm', mm: 14.5 },
  { screw: 'M18 × 1.5', tap: '16.5 mm', mm: 16.5 },
  { screw: 'M20 × 1.5', tap: '18.5 mm', mm: 18.5 },
];

export const npt = [
  { pipe: '1/8-27 NPT', tap: 'R', inch: 0.339, note: 'Often 11/32 (0.3438) in hardware-store charts' },
  { pipe: '1/4-18 NPT', tap: '7/16', inch: 0.4375 },
  { pipe: '3/8-18 NPT', tap: '37/64', inch: 0.5781 },
  { pipe: '1/2-14 NPT', tap: '23/32', inch: 0.7188 },
  { pipe: '3/4-14 NPT', tap: '59/64', inch: 0.9219 },
  { pipe: '1-11.5 NPT', tap: '1-5/32', inch: 1.1562 },
];

/** Highlight pages for high-volume queries. */
export const popular = [
  { slug: '1-4-20', title: '1/4-20 tap drill', screw: '1/4-20', tap: '#7 (0.201″)', series: 'UNC' },
  { slug: '10-24', title: '10-24 tap drill', screw: '10-24', tap: '#25 (0.1495″)', series: 'UNC' },
  { slug: '10-32', title: '10-32 tap drill', screw: '10-32', tap: '#21 (0.159″)', series: 'UNF' },
  { slug: '8-32', title: '8-32 tap drill', screw: '8-32', tap: '#29 (0.136″)', series: 'UNC' },
  { slug: '6-32', title: '6-32 tap drill', screw: '6-32', tap: '#36 (0.1065″)', series: 'UNC' },
  { slug: 'm3', title: 'M3 tap drill', screw: 'M3 × 0.5', tap: '2.5 mm', series: 'Metric coarse' },
  { slug: 'm4', title: 'M4 tap drill', screw: 'M4 × 0.7', tap: '3.3 mm', series: 'Metric coarse' },
  { slug: 'm5', title: 'M5 tap drill', screw: 'M5 × 0.8', tap: '4.2 mm', series: 'Metric coarse' },
  { slug: 'm6', title: 'M6 tap drill', screw: 'M6 × 1.0', tap: '5.0 mm', series: 'Metric coarse' },
  { slug: 'm8', title: 'M8 tap drill', screw: 'M8 × 1.25', tap: '6.8 mm', series: 'Metric coarse' },
  { slug: 'm10', title: 'M10 tap drill', screw: 'M10 × 1.5', tap: '8.5 mm', series: 'Metric coarse' },
];
