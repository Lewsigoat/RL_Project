/** Nominal drill diameters in inches. Number and letter sizes follow ASME B94.11M / common jobber charts. */

export const numbered = [
  [1, 0.228], [2, 0.221], [3, 0.213], [4, 0.209], [5, 0.2055],
  [6, 0.204], [7, 0.201], [8, 0.199], [9, 0.196], [10, 0.1935],
  [11, 0.191], [12, 0.189], [13, 0.185], [14, 0.182], [15, 0.18],
  [16, 0.177], [17, 0.173], [18, 0.1695], [19, 0.166], [20, 0.161],
  [21, 0.159], [22, 0.157], [23, 0.154], [24, 0.152], [25, 0.1495],
  [26, 0.147], [27, 0.144], [28, 0.1405], [29, 0.136], [30, 0.1285],
  [31, 0.12], [32, 0.116], [33, 0.113], [34, 0.111], [35, 0.11],
  [36, 0.1065], [37, 0.104], [38, 0.1015], [39, 0.0995], [40, 0.098],
  [41, 0.096], [42, 0.0935], [43, 0.089], [44, 0.086], [45, 0.082],
  [46, 0.081], [47, 0.0785], [48, 0.076], [49, 0.073], [50, 0.07],
  [51, 0.067], [52, 0.0635], [53, 0.0595], [54, 0.055], [55, 0.052],
  [56, 0.0465], [57, 0.043], [58, 0.042], [59, 0.041], [60, 0.04],
  [61, 0.039], [62, 0.038], [63, 0.037], [64, 0.036], [65, 0.035],
  [66, 0.033], [67, 0.032], [68, 0.031], [69, 0.02925], [70, 0.028],
  [71, 0.026], [72, 0.025], [73, 0.024], [74, 0.0225], [75, 0.021],
  [76, 0.02], [77, 0.018], [78, 0.016], [79, 0.0145], [80, 0.0135],
].map(([n, inch]) => ({
  label: `#${n}`,
  family: 'number',
  inch,
  mm: +(inch * 25.4).toFixed(3),
}));

export const letter = [
  ['A', 0.234], ['B', 0.238], ['C', 0.242], ['D', 0.246], ['E', 0.25],
  ['F', 0.257], ['G', 0.261], ['H', 0.266], ['I', 0.272], ['J', 0.277],
  ['K', 0.281], ['L', 0.29], ['M', 0.295], ['N', 0.302], ['O', 0.316],
  ['P', 0.323], ['Q', 0.332], ['R', 0.339], ['S', 0.348], ['T', 0.358],
  ['U', 0.368], ['V', 0.377], ['W', 0.386], ['X', 0.397], ['Y', 0.404],
  ['Z', 0.413],
].map(([label, inch]) => ({
  label,
  family: 'letter',
  inch,
  mm: +(inch * 25.4).toFixed(3),
}));

function gcd(a, b) {
  return b ? gcd(b, a % b) : a;
}

export const fractional = [];
for (let n = 1; n <= 64; n += 1) {
  const g = gcd(n, 64);
  const num = n / g;
  const den = 64 / g;
  if (den > 1 || n === 64) {
    const inch = n / 64;
    fractional.push({
      label: den === 1 ? '1' : `${num}/${den}`,
      family: 'fraction',
      inch,
      mm: +(inch * 25.4).toFixed(3),
    });
  }
}

const commonMm = [
  0.5, 0.6, 0.8, 1, 1.2, 1.5, 1.6, 1.8, 2, 2.5, 3, 3.2, 3.3, 3.5, 4, 4.2, 4.5,
  5, 5.5, 6, 6.5, 6.8, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.2, 10.5, 11, 12, 12.5, 13,
];

function metricRow(mm) {
  return {
    label: `${Number(mm.toFixed(1))} mm`,
    family: 'metric',
    mm,
    inch: +(mm / 25.4).toFixed(4),
  };
}

export const metric = commonMm.map(metricRow);

export const metricGrid = [];
for (let t = 5; t <= 200; t += 1) {
  metricGrid.push(metricRow(t / 10));
}

export const allBits = [...numbered, ...letter, ...fractional, ...metric];

export function nearest(inch, family) {
  const pool = family ? allBits.filter((b) => b.family === family) : allBits;
  return pool.reduce((best, b) => {
    const d = Math.abs(b.inch - inch);
    return !best || d < best.delta ? { bit: b, delta: d } : best;
  }, null);
}
