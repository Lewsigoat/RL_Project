/**
 * Brand notes are starting points, not a substitute for measuring the stem.
 * "confirmed" = named in a manufacturer support page or the brand's own fitting article.
 * "commonly reported" = consistent aftermarket / retailer documentation; still measure.
 */
export const brands = [
  {
    slug: 'sun-joe',
    name: 'Sun Joe',
    typical: 'M22-15 mm on many electric hose/outlet connections',
    confidence: 'confirmed',
    source: 'Shop Joe hose compatibility and accessory FAQs describe M22-15 mm on the unit outlet and list M22 14 mm / 15 mm accessories.',
    notes: [
      'A hardware-store M22-14 mm hose often threads on and then leaks under pressure.',
      'The usual fix is an M22-15 mm ↔ M22-14 mm coupler, then a standard 14 mm hose or 3/8″ QC kit.',
    ],
    measure: 'Measure the male stem or the female bore. Do not trust the word “M22” on the Amazon title.',
  },
  {
    slug: 'ar-blue-clean',
    name: 'AR Blue Clean',
    typical: 'Mix of M22-14 mm and M22-15 mm; the brand documents both',
    confidence: 'confirmed',
    source: 'AR Blue Clean “Get Connected” article (2026) explains stem ID and sells 14↔15 transfer adapters.',
    notes: [
      'Their own article is the clearest OEM write-up of why the threads engage but the O-ring does not.',
      'Electric AR units are often 15 mm; do not assume every AR hose in a kit is 15 mm on both ends.',
    ],
    measure: 'Measure the pump outlet and the gun inlet separately. Kits are not always matched.',
  },
  {
    slug: 'ryobi',
    name: 'Ryobi',
    typical: 'Gas machines often M22-14 mm; some electric units use 15 mm',
    confidence: 'commonly reported',
    source: 'No single Ryobi support article owned the SERP. Aftermarket fitment lists split by gas vs electric.',
    notes: [
      'Treat Ryobi as “measure it.” Model families are not consistent enough to buy blind.',
      'Once identified, a 14 mm hose plus 1/4″ QC on the wand is a common upgrade path.',
    ],
    measure: 'Pull the hose, measure the stem on the gun and the bore on the pump.',
  },
  {
    slug: 'karcher',
    name: 'Kärcher',
    typical: 'K-series electrics: proprietary clip. Many gas / pro units: M22 or QC',
    confidence: 'confirmed',
    source: 'K-series aftermarket adapters are sold as clip (male) to M22-14 mm. Kärcher US accessory pages use “Quick Connect” language for K-series.',
    notes: [
      'A “universal M22 hose” will not clip onto a K2–K7 without the adapter.',
      'Kärcher professional and gas lines are a different ecosystem — do not buy a K-series clip for a gas Honda-powered unit.',
    ],
    measure: 'If you see a sliding collar and no big knurled nut, it is probably the K clip.',
  },
  {
    slug: 'simpson',
    name: 'Simpson',
    typical: 'Gas consumer units commonly M22-14 mm at hose and gun',
    confidence: 'commonly reported',
    source: 'Aftermarket 14 mm M22 hoses are the default listing for Simpson consumer gas machines.',
    notes: [
      'Higher-end Simpson / AAA units may already ship with 3/8″ QC on the hose.',
      'Match PSI and hose ID (1/4″ vs 3/8″) as well as the connector.',
    ],
    measure: 'Still measure. A rebranded pump or a replacement gun can change the inlet.',
  },
  {
    slug: 'greenworks',
    name: 'Greenworks',
    typical: 'Electric units are a mix of M22-14 mm and M22-15 mm',
    confidence: 'commonly reported',
    source: 'Retailer Q&A and hose listings disagree by model; no single OEM chart.',
    notes: [
      'Buy the hose last. Identify the pump and gun first.',
      'If both ends are M22 but one leaks, you likely have a 14/15 mismatch, not a “bad hose.”',
    ],
    measure: 'Caliper the stem. Greenworks model numbers are not a reliable size code.',
  },
  {
    slug: 'craftsman-dewalt',
    name: 'Craftsman and DeWalt',
    typical: 'Gas units commonly M22-14 mm; electric units vary',
    confidence: 'commonly reported',
    source: 'Shared OEM platforms show up with 14 mm aftermarket hoses. Confirm per model.',
    notes: [
      'These brands share pumps with other big-box labels. The sticker is not the fitting standard.',
      'A 14 mm M22 → 3/8″ QC adapter on the pump is a typical shop conversion.',
    ],
    measure: 'Measure both ends of the stock hose. They are not always the same.',
  },
  {
    slug: 'generac-powerstroke',
    name: 'Generac and PowerStroke',
    typical: 'PowerStroke gas often M22-14 mm; some Generac electrics reported as 15 mm',
    confidence: 'commonly reported',
    source: 'Aftermarket coupler listings call out Generac / PowerStroke in the 14 mm or 15 mm families separately.',
    notes: [
      'Do not copy a neighbor’s hose. The two brand names are not one standard.',
      'If a new gun wobbles on the hose, stop and measure before you run pressure.',
    ],
    measure: 'Stem first, Amazon title second.',
  },
];
