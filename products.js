/**
 * Alipen Solutions Agency Ltd - Official Product Catalog Dataset
 * Brand: Alipen Solutions Agency Ltd ("--Empowering Health Solutions--")
 * Official Contact: Peter Ogettoh | +254 712 272 463 | info@alipen.co.ke | Nairobi, Kenya
 */

const PRODUCT_CATEGORIES = [
  { id: 'all', name: 'All Products', icon: 'grid' },
  { id: 'imaging', name: 'Radiology & Medical Imaging', icon: 'film' },
  { id: 'critical', name: 'Critical Care & Patient Monitoring', icon: 'activity' },
  { id: 'outpatient', name: 'Outpatient & Diagnostics', icon: 'stethoscope' },
  { id: 'surgical', name: 'Surgical & Disposables', icon: 'package' },
  { id: 'furniture', name: 'Hospital Furniture', icon: 'truck' }
];

const PRODUCTS = [
  {
    id: 1,
    slug: 'patient-monitor',
    name: 'Patient Monitor (Multi-Parameter Bedside Monitor)',
    shortName: 'Patient Monitor',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Real-time Vital Sign Monitoring for Better Critical Care',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'Hospital Essential',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'Advanced multi-parameter bedside patient monitor designed for high-acuity wards, operating theatres, intensive care (ICU), high dependency units (HDU), and emergency triage. Delivers accurate real-time waveforms and numerical data for ECG, SpO2, NIBP, respiration rate, and dual-channel temperature.',
    features: [
      '12.1-inch high-resolution color TFT screen with multi-waveform display',
      'Standard parameters: 5-Lead ECG, Non-Invasive Blood Pressure (NIBP), SpO2, Respiration Rate, Dual-Channel Temp, Pulse Rate',
      'Built-in rechargeable lithium-ion battery providing up to 4 hours of continuous operation',
      'Audible and visual multi-level alarms with user-configurable thresholds',
      '72-hour trend review and graphic/tabular trend data storage',
      'Defibrillation and electrosurgical interference protection',
      'Bedside wall-mount and mobile trolley stand compatible'
    ],
    specs: {
      'Display': '12.1" Color TFT LCD, 800 x 600 resolution',
      'ECG': '5-lead (RA, LA, RL, LL, V); Lead selection: I, II, III, aVR, aVL, aVF, V',
      'NIBP Method': 'Automatic Oscillometric; Modes: Manual, Auto, Continuous',
      'SpO2 Range': '0 - 100% (Resolution: 1%, Accuracy: ±2% at 70-100%)',
      'Pulse Rate': '20 - 250 bpm (Accuracy: ±2 bpm)',
      'Temperature': 'Dual-channel, 0 - 50°C (Accuracy: ±0.1°C)',
      'Power Supply': 'AC 100-240V, 50/60Hz; Internal 14.8V Rechargeable Li-ion battery',
      'Certifications': 'CE Certified, ISO 13485, Medical Electrical Safety Compliant'
    },
    applications: [
      'Intensive Care Units (ICU) and High Dependency Units (HDU)',
      'Accident & Emergency Casualty (A&E) resuscitation bays',
      'Operating Theatres (OT) and Post-Anesthesia Care Units (PACU)',
      'General hospital inpatient monitoring wards'
    ],
    packaging: '1 Complete Unit including 5-lead ECG cable, Adult NIBP cuff with extension tube, Adult finger SpO2 sensor, Skin temperature probe, Ground wire, Power cord, and English Operating Manual.'
  },
  {
    id: 33,
    slug: 'contec-e12-ecg',
    name: 'CONTEC E12 Electrocardiograph (12-Channel ECG Machine)',
    shortName: 'CONTEC E12 ECG Machine',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Professional 12-channel ECG acquisition, analysis, and recording.',
    image: 'public/images/catalogue/image_56.png',
    thumbnail: 'public/images/catalogue/image_56.png',
    badge: 'New Arrival',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'A professional, high-resolution 12-channel ECG machine featuring simultaneous acquisition, advanced digital filtering, a built-in thermal printer, and extensive ECG record storage.',
    features: [
      '12-Channel simultaneous acquisition & analysis for accurate cardiac assessment',
      'High-resolution color LCD screen with real-time waveform display',
      'Built-in high-speed thermal printer with multiple print formats',
      'Smart Data Storage: For 1000+ ECG records, allowing easy review and print',
      'Advanced digital filtering to eliminate interference and ensure precise results',
      'Automated ECG measurement, analysis, and interpretation to assist clinical staff',
      'User-friendly, portable console design with a simple interface for hospitals, clinics, and home use',
      'Includes essential patient lead cables, chest/limb electrodes, thermal paper, and a power supply'
    ],
    specs: {
      'Model': 'CONTEC E12',
      'Voltage': '100V-240V~, 50Hz/60Hz',
      'Power Input': '≤ 100VA',
      'Safety Class': 'Class I, Type CF',
      'Display': 'Large high-resolution color LCD',
      'Acquisition Type': '12-Channel simultaneity',
      'Storage': 'Internal Memory (holds 1000+ records)',
      'Standard Accessories': '12-lead patient cable, chest electrodes, limb clamps, thermal recording paper, power cord'
    },
    applications: [
      'Hospitals and cardiac care units',
      'Clinics and outpatient diagnostic facilities',
      'Portable ECG assessment and home use'
    ],
    accessories: [
      'CONTEC E12 ECG machine unit',
      '12-lead patient cable',
      'Chest electrodes',
      'Limb clamps',
      'Thermal recording paper',
      'Power cord / power supply'
    ],
    packaging: 'Complete ECG machine set with patient lead cable, chest electrodes, limb clamps, thermal recording paper, and power cord.'
  },
  {
    id: 2,
    slug: 'quip-oxygen-concentrator-5l',
    name: 'QUIP Oxygen Concentrator (5L Medical-Grade)',
    shortName: 'QUIP Oxygen Concentrator (5L)',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Reliable Oxygen. Brighter Lives. Continuous Hospital Purity.',
    image: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    thumbnail: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    badge: 'High Demand',
    leadTime: 'In Stock - Ready for Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'The QUIP 5-Litre Medical-Grade Oxygen Concentrator delivers continuous, stable 93% ± 3% medical oxygen directly from ambient air using advanced Pressure Swing Adsorption (PSA) technology. Designed for relentless hospital ward service, respiratory triage, nursing facilities, and patient home therapy.',
    features: [
      'Continuous 1 to 5 Litres/minute flow rate with precision calibrated flowmeter',
      'High oxygen concentration: 93% ± 3% across all output flow rates',
      'Large LCD display indicating accumulated runtime and operating hours',
      'Comprehensive safety alarms: Power failure, high/low pressure, purity sensor alert, overheating',
      'Ultra-quiet oil-free compressor engineered for 24/7 continuous operation (<45 dB)',
      'Four heavy-duty smooth-swivel castor wheels with ergonomic transport handle',
      'Integrated recessed dock for humidification bottle preventing accidental knockovers'
    ],
    specs: {
      'Flow Rate': '0.5 – 5.0 L/min (Continuous)',
      'Oxygen Concentration': '93% ± 3% at all rated flows',
      'Output Pressure': '0.04 – 0.07 MPa (40 – 70 kPa)',
      'Sound Level': '≤ 45 dBA whisper-quiet operation',
      'Power Consumption': '350W average (AC 220V ± 10%, 50Hz)',
      'Filtration System': 'Multi-stage: Gross particle filter, HEPA intake filter, bacterial filter',
      'Dimensions & Weight': '380mm x 340mm x 690mm; Net weight ~19.5 kg',
      'Certifications': 'CE Medical Grade, ISO 13485 Registered'
    },
    applications: [
      'Hospital respiratory care, medical and pediatric wards',
      'Sub-county and county referral facility oxygen therapy',
      'Emergency room stabilization and ambulance support',
      'Home care oxygen therapy for chronic COPD and cardiopulmonary patients'
    ],
    packaging: '1 QUIP 5L Oxygen Concentrator Unit, 1 Reusable Humidifier Bottle, 2 Adult Nasal Cannulas, 1 Intake Filter Replacement Set, and User Operating Manual.'
  },
  {
    id: 3,
    slug: 'ent-diagnostic-set',
    name: 'ENT Diagnostic Set (Otoscope & Ophthalmoscope Kit)',
    shortName: 'ENT Diagnostic Set',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Accurate Clinical Diagnosis. Improved Patient Outcomes.',
    image: 'public/images/catalogue/ent-diagnostic-set-hd.png',
    thumbnail: 'public/images/catalogue/ent-diagnostic-set-hd.png',
    badge: 'Clinical Sourcing',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'Professional comprehensive Ear, Nose & Throat (ENT) diagnostic instrument set containing high-precision optical otoscope, direct ophthalmoscope, bent-arm throat illuminator, and reusable specula, all enclosed in a deluxe protective hard-shell case.',
    features: [
      'Fiber-optic halogen / LED illumination delivering true tissue color rendition and zero shadow',
      'Direct ophthalmoscope head with precision aperture selection and diopter lens correction range (-20D to +20D)',
      'Otoscope head with 3x swivel viewing magnification lens and insufflation bulb port',
      'Bayonet locking mechanism for rapid, secure instrument head interchangeability',
      'Includes bent-arm illuminator, reusable nasal speculum adaptor, and tongue blade holder',
      'Packaged in a durable, shock-resistant molded hard presentation case'
    ],
    specs: {
      'Optical Illumination': 'Fiber-optic cool light transmission with halogen/LED lamp',
      'Diopter Range': '-20D to +20D (29 corrective lenses)',
      'Apertures': 'Large spot, small spot, semi-circle, red-free filter, fixation star',
      'Otoscope Specula Sizes': 'Reusable sizes: 2.5mm, 3.0mm, 4.0mm, 5.0mm',
      'Power Source': 'Standard C-cell battery handle or rechargeable handle',
      'Casing Material': 'High-impact molded plastic interior with foam protective recess'
    },
    applications: [
      'Outpatient consulting rooms and specialist ENT clinics',
      'General practice, pediatric check-ups, and casualty triage',
      'Ophthalmic screening and fundoscopy examinations',
      'Medical schools and clinical training centers'
    ],
    packaging: '1 Battery Handle, 1 Otoscope Head, 1 Ophthalmoscope Head, 1 Nasal Speculum, 1 Bent Arm Illuminator, 2 Laryngeal Mirrors, 1 Tongue Blade Bracket, Tube of Reusable Specula, Spare Bulbs, Deluxe Hard Storage Case.'
  },
  {
    id: 4,
    slug: 'dry-medical-xray-film',
    name: "'DRY' Medical X-Ray Film (Radiology Imaging Media)",
    shortName: "'DRY' Medical X-Ray Film",
    category: 'imaging',
    categoryLabel: 'Medical Imaging & Printing Media',
    tagline: 'Consistent Contrast. High Dmax. Reliable Diagnostic Radiography.',
    image: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    thumbnail: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    badge: 'Radiology Standard',
    leadTime: 'In Stock - Multiple Sizes Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'High-definition direct thermal medical dry imaging film designed for modern daylight diagnostic radiology. Formulated with a premium blue polyester base and high silver-equivalent contrast layer, delivering exceptional maximum optical density (Dmax > 3.0) and ultra-fine grain reproduction for definitive clinical diagnosis.',
    features: [
      'Daylight loading convenience: 100% chemical-free dry thermal processing with zero darkroom chemicals',
      'Neutral-black image tone providing outstanding bone trabecular and soft-tissue detail',
      'High scratch resistance and anti-static surface coating preventing transport jams in thermal imagers',
      'Long-term archival stability: Diagnostic grade longevity conforming to international radiology standards',
      'Universal compatibility with leading dry laser and dry thermal medical imagers'
    ],
    specs: {
      'Base Material': 'Optically clear blue-tinted polyester (PET) base (approx. 175 µm thickness)',
      'Optical Density': 'Dmax ≥ 3.0, Dmin ≤ 0.22',
      'Available Sizes': '14" x 17" (35x43cm), 11" x 14" (28x35cm), 10" x 12" (25x30cm), 8" x 10" (20x25cm)',
      'Storage Conditions': '10°C – 25°C, Relative Humidity 30% – 60%, avoid ionizing radiation and direct sunlight',
      'Processing Technology': 'Direct dry thermal / Dry laser imaging'
    },
    applications: [
      'Digital Radiography (DR) and Computed Radiography (CR) printing',
      'Hospital radiology and diagnostic imaging centers',
      'Orthopedic, chest, mammography, and abdominal X-ray documentation',
      'Surgical and referral reporting'
    ],
    packaging: '100 sheets per light-tight protective carton, packed in reinforced outer cases.'
  },
  {
    id: 5,
    slug: 'judcare-thermal-film',
    name: 'JUDcare Medical Dry Thermal Film',
    shortName: 'JUDcare Thermal Film',
    category: 'imaging',
    categoryLabel: 'Medical Imaging & Printing Media',
    tagline: 'High-Resolution Grayscale Thermal Imaging for CT, MRI & DR.',
    image: 'public/images/catalogue/judcare-thermal-film-hd.png',
    thumbnail: 'public/images/catalogue/judcare-thermal-film-hd.png',
    badge: 'CE Certified',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'JUDcare Medical Dry Thermal Film is engineered for advanced medical dry printers, providing high-contrast diagnostic films for CT, MRI, Ultrasound, and Digital Radiography. Certified CE with anti-static and anti-fog layers for flawless film transport.',
    features: [
      'Engineered specifically for JUDcare and compatible medical thermal dry printers',
      'High dynamic range and wide grayscale gradient ensuring subtle lesion identification',
      'Smooth surface finish preventing roller friction and jam artifacts',
      'Water-resistant and smudge-proof image retention',
      'Packaged in light-barrier foil envelope'
    ],
    specs: {
      'Film Base': 'Medical-grade polyester base with thermal sensitive silver-salt emulsion',
      'Density Performance': 'Maximum Optical Density Dmax ≥ 3.2',
      'Moisture Barrier': 'Multi-layer vacuum foil inner packaging',
      'Standard Sizes': '14" x 17", 11" x 14", 8" x 10"',
      'Certifications': 'CE Medical, ISO 9001 / ISO 13485'
    },
    applications: [
      'Computed Tomography (CT) scans',
      'Magnetic Resonance Imaging (MRI) diagnostic prints',
      'Digital Subtraction Angiography (DSA)',
      'General radiography outpatient reporting'
    ],
    packaging: '100 Sheets per box enclosed in light-protective vacuum aluminum foil.'
  },
  {
    id: 6,
    slug: 'aurion-ak808-thermal-film',
    name: 'AURION AK-808 Imaging Thermal Film',
    shortName: 'AURION AK-808 Thermal Film',
    category: 'imaging',
    categoryLabel: 'Medical Imaging & Printing Media',
    tagline: 'Reliable Medical Printing for Accurate Radiology & Ultrasound Diagnosis.',
    image: 'public/images/catalogue/aurion-ak808-thermal-film-hd.png',
    thumbnail: 'public/images/catalogue/aurion-ak808-thermal-film-hd.png',
    badge: 'Diagnostic Grade',
    leadTime: 'In Stock - Multiple Sizes',
    priceEstimate: 'Request Institutional Quote',
    description: 'AURION AK-808 Imaging Thermal Film is a trusted medical dry imaging film delivering rapid thermal image development, ultra-sharp edge definition, and stable gray density for radiology and clinical ultrasound reporting.',
    features: [
      'High thermal sensitivity for rapid dry print generation without odor or waste chemicals',
      'Accurate reproduction of bone structures, pulmonary fields, and vascular pathways',
      'Anti-static backcoat preventing static discharge and dust attraction',
      'Durable archival film base with high physical tensile strength',
      'Sealed in moisture-proof, light-shielded foil packets'
    ],
    specs: {
      'Model': 'AURION AK-808 Series',
      'Film Type': 'Dry Thermal Medical Film',
      'Base Thickness': '180 µm Blue PET Polyester',
      'Resolution': 'Sub-millimeter detail reproduction (up to 508 DPI compatible)',
      'Shelf Life': '24 Months under standard storage conditions (10°C – 23°C)'
    },
    applications: [
      'Ultrasound, echocardiography, and Doppler imaging output',
      'Mobile and fixed X-ray reporting stations',
      'County hospital and private diagnostic clinic radiology suites'
    ],
    packaging: '100 Sheets per protective box with inner light-tight pouch.'
  },
  {
    id: 7,
    slug: 'sony-upp-110hg-thermal-print-media',
    name: 'Sony UPP-110HG Thermal Print Media (Type V High Glossy)',
    shortName: 'Sony UPP-110HG Print Media',
    category: 'imaging',
    categoryLabel: 'Medical Imaging & Printing Media',
    tagline: 'High-Gloss Ultrasound Print Media for Clinical Precision.',
    image: 'public/images/catalogue/sony-upp-110hg-thermal-print-media-hd.png',
    thumbnail: 'public/images/catalogue/sony-upp-110hg-thermal-print-media-hd.png',
    badge: 'Original Standard',
    leadTime: 'In Stock - Box of 10 Rolls',
    priceEstimate: 'Request Institutional Quote',
    description: 'Original Sony UPP-110HG (Type V High Glossy) is the gold standard medical recording paper designed for A6 monochrome thermal video printers. Produces near-photographic high-gloss diagnostic ultrasound prints with deep blacks and superior durability.',
    features: [
      'High-gloss coating provides 25% higher glossiness than standard paper',
      'Water-resistant and finger-print resistant protective topcoat',
      'Anti-curling technology ensures flat, clean prints suitable for medical files',
      'High humidity and heat resistance preserves image integrity for years',
      'Minimal printhead wear due to calibrated protective lubricant layer'
    ],
    specs: {
      'Paper Dimensions': '110 mm (Width) x 18 m (Length) per roll',
      'Print Yield': 'Approx. 190 to 240 prints per roll depending on print format',
      'Paper Type': 'Type V (High Glossy)',
      'Printer Compatibility': 'Sony UP-895MD, UP-897MD, UP-D897, UP-X898MD, UP-D898MD and compatible Mitsubishi video printers',
      'Origin': 'Original Certified Sony Medical Media'
    },
    applications: [
      'Obstetric and gynecological ultrasound printouts',
      'Abdominal, vascular, and cardiac echocardiography reports',
      'Endoscopy and microscopy image hardcopies',
      'Patient case file documentation'
    ],
    packaging: 'Individual roll sealed in protective aluminum foil; 10 rolls per outer box.'
  },
  {
    id: 8,
    slug: 'blue-ink-jet-film-8x10',
    name: 'Blue Ink Jet Film (8x10 inch / 20x25cm, NIF 100)',
    shortName: 'Blue Ink Jet Film (8x10)',
    category: 'imaging',
    categoryLabel: 'Medical Imaging & Printing Media',
    tagline: 'Sharp Medical Images. Fast Drying. Cost-Effective Clinic Printing.',
    image: 'public/images/catalogue/blue-ink-jet-film-hd.png',
    thumbnail: 'public/images/catalogue/blue-ink-jet-film-hd.png',
    badge: 'Cost Efficient',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'Medical blue-base inkjet printing film specially treated with a nanoporous coating for instant ink absorption and instant dry output. Formulated for standard medical inkjet printers (Epson, Canon) to deliver affordable, high-contrast radiography and ultrasound images without requiring expensive laser printers.',
    features: [
      'Nanoporous microporous coating guarantees rapid ink drying with zero smudge',
      'Blue-tinted medical grade polyester base replicates traditional darkroom X-ray appearance',
      'High Dmax density producing deep blacks and distinct anatomical boundaries',
      'Waterproof and anti-scratch surface once printed',
      'Significantly lowers operating expenditure for regional clinics and private radiology centers'
    ],
    specs: {
      'Sheet Size': '8" x 10" (203 mm x 254 mm)',
      'Quantity': 'NIF 100 (100 sheets per pack)',
      'Base Thickness': '180 – 210 µm Blue PET Polyester',
      'Ink Compatibility': 'Dye and Pigment water-based inkjet inks',
      'Expiry / Stability': 'Long shelf stability (>3 years unopened)'
    },
    applications: [
      'Dental panoramic and intraoral X-ray prints',
      'Clinic ultrasound scan reports',
      'Minor orthopedic and extremities digital X-ray prints',
      'Affordable imaging in outpatient health centers'
    ],
    packaging: '100 Sheets per pack in sealed light-protective foil packet with sturdy outer box.'
  },
  {
    id: 9,
    slug: 'rosmed-ultrasound-coupling-gel-5kg',
    name: 'ROSMED Ultrasound Transmission Coupling Gel (5KG + Dispenser)',
    shortName: 'ROSMED Ultrasound Gel (5KG)',
    category: 'imaging',
    categoryLabel: 'Radiology & Medical Imaging',
    tagline: 'Superior Acoustic Conductivity for Clear, Distortion-Free Diagnostic Imaging.',
    image: 'public/images/catalogue/rosmed-ultrasound-coupling-gel-hd.png',
    thumbnail: 'public/images/catalogue/rosmed-ultrasound-coupling-gel-hd.png',
    badge: 'Made in Kenya',
    leadTime: 'In Stock - High Volume Supply',
    priceEstimate: 'Request Institutional Quote',
    description: 'ROSMED Professional Medical Ultrasound Transmission Coupling Gel is manufactured in Kenya to strict pharmaceutical and clinical standards. Provides optimal acoustic impedance matching between transducer and skin, ensuring crystal-clear imaging without bubbles, skin irritation, or transducer damage.',
    features: [
      'Acoustically correct impedance for the broad range of ultrasound frequencies used in diagnostic scanning',
      'Completely aqueous formulation: 100% water-soluble, non-staining to clothing, and easy to wipe clean',
      'Hypoallergenic, non-irritating, and bacteriostatic: Safe for sensitive and obstetric patients',
      'Salt-free and formaldehyde-free formulation that will not corrode ultrasound transducer heads',
      'Economical 5 KG bulk canister supplied with a free 250ml squeezable clinic refill bottle and dispensing spout'
    ],
    specs: {
      'Capacity': '5 Kilograms (5KG Cubitainer / Canister)',
      'Included Accessories': '1 Empty 250ml clinic dispensing bottle + 1 Funnel refill cap spigot',
      'pH Range': '6.5 – 7.2 (Neutral, skin-compatible)',
      'Viscosity': 'Optimized high-viscosity gel (will not run down during examinations)',
      'Formulation': 'Bacteriostatic, water-soluble, hypoallergenic, bubble-free',
      'Origin': 'Proudly Manufactured in Kenya'
    },
    applications: [
      'Obstetric, fetal, and gynecological ultrasound examinations',
      'Abdominal, pelvic, and musculoskeletal sonography',
      'Vascular Doppler examinations and fetal heart monitoring',
      'Physiotherapy and cavitation therapeutic procedures'
    ],
    packaging: '5 KG heavy-duty canister + 1 dispenser bottle + 1 refill cap per box. Wholesale carton packs of 4 canisters available.'
  },
  {
    id: 10,
    slug: 'medex-steri-gauze-absorbent-cotton',
    name: 'MEDEX Steri Gauze (Absorbent Cotton Gauze Rolls)',
    shortName: 'MEDEX Steri Gauze Rolls',
    category: 'surgical',
    categoryLabel: 'Surgical & Disposables',
    tagline: 'Trusted Wound Care & Surgical Absorption for Everyday Hospital Protection.',
    image: 'public/images/catalogue/medex-steri-gauze-hd.png',
    thumbnail: 'public/images/catalogue/medex-steri-gauze-hd.png',
    badge: 'Clinical Sourcing',
    leadTime: 'In Stock - Bulk Sourcing',
    priceEstimate: 'Request Institutional Quote',
    description: 'MEDEX Steri Gauze Absorbent Cotton Gauze Rolls are produced from 100% pure bleached surgical cotton. Delivers rapid liquid absorbency, ultra-soft texture, and minimal linting for surgical dressing, wound debridement, and general clinical absorption.',
    features: [
      '100% pure bleached virgin cotton with zero optical brighteners or chemical residues',
      'High absorbency rate (sinks within 10 seconds), absorbing up to 23 times its weight in exudate',
      'Soft and skin-friendly mesh structure providing breathability and comfort over open wounds',
      'Uniform weave with clean selvedges that minimize loose threads and lint shedding',
      'Individually wrapped in signature blue protective paper with green Medex Steri Gauze quality seal'
    ],
    specs: {
      'Material': '100% Bleached Absorbent Cotton Gauze',
      'Standard Dimensions': 'Available in 90cm x 100m, 90cm x 50m, and surgical roll cuts',
      'Absorbency Speed': 'Under 10 seconds (standard British Pharmacopoeia BP test)',
      'Whiteness': '≥ 80% whiteness degree without chemical fluorescence',
      'Sterilization': 'Suitable for steam autoclave and EO gas sterilization'
    },
    applications: [
      'Hospital operating theatres (theatre packs and surgical swabbing)',
      'Post-operative wound dressing and emergency wound packing',
      'Maternity, casualty, and minor procedure rooms',
      'First aid stations, medical clinics, and school dispensaries'
    ],
    packaging: 'Individually wrapped roll in protective moisture-barrier blue paper; packed in bundles or cartons for institutional procurement.'
  },
  {
    id: 11,
    slug: 'medical-emergency-trolley-crash-cart',
    name: 'Medical Emergency Trolley / Crash Cart (Multi-Drawer)',
    shortName: 'Emergency Crash Cart Trolley',
    category: 'furniture',
    categoryLabel: 'Hospital Furniture & Emergency',
    tagline: 'Rapid Clinical Response. Ready for Critical Life-Saving Care.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Hospital Furniture',
    leadTime: 'In Stock - Assembled / Ready to Deploy',
    priceEstimate: 'Request Institutional Quote',
    description: 'Heavy-duty medical crash cart engineered for emergency resuscitation and rapid intervention in acute care settings. Features a robust aluminum alloy and ABS polymer frame, 5 smooth gliding color-coded drawers with central key locking, defibrillator swivel tray, oxygen cylinder bracket, and telescopic IV pole.',
    features: [
      'Durable ABS engineered plastic tabletop with integrated raised anti-spill guardrails',
      'Five multi-depth sliding drawers (2 small, 2 medium, 1 large) with internal divider sets for organized medication and ampoule storage',
      'Centralized gang locking mechanism securing all drawers with single key or break-away security seal',
      'Top-mounted 360° swivel defibrillator shelf with safety strap for secure cardiac monitor placement',
      'Stainless steel height-adjustable IV infusion pole with 4 hooks',
      'CPR cardiac board mounted on cart back for immediate chest compression deployment',
      'Oxygen cylinder tank holder bracket, dual waste receptacles, and sharps container bracket',
      'Four 100mm heavy-duty anti-static noiseless castor wheels with independent cross brakes'
    ],
    specs: {
      'Dimensions': '750mm (L) x 480mm (W) x 930mm (H) - Tabletop height (excluding IV pole)',
      'Drawers': '5 Drawers on smooth ball-bearing soft-closing drawer slides with transparent label slots',
      'Frame Material': 'High-tensile aluminum column structure with impact-resistant ABS composite',
      'Castors': '4 Swivel castors (100mm diameter), 2 wheels equipped with foot-pedal brakes',
      'Accessories Included': 'Defibrillator shelf, IV pole, CPR cardiac board, Sharps bin, Dual waste bins, Oxygen cylinder cage, Sliding side extension shelf'
    },
    applications: [
      'Accident & Emergency Casualty (A&E) and Resuscitation bays',
      'Intensive Care Units (ICU), Coronary Care Units (CCU), HDU',
      'Operating Theatres (OT) and Post-Anesthesia Recovery',
      'General hospital ward rapid response crash stations'
    ],
    packaging: '1 Complete Emergency Trolley Cart with all modular accessory attachments and drawer dividers, safely boxed and cushioned.'
  },
  {
    id: 12,
    slug: 'ecg-recording-paper',
    name: 'ECG Recording Paper (Z-Fold & Rolls)',
    shortName: 'ECG Recording Paper',
    category: 'imaging',
    categoryLabel: 'Radiology & Medical Imaging',
    tagline: 'Compatible Z-fold and roll formats for clinical ECG printers.',
    image: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    thumbnail: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    badge: 'Consumable',
    leadTime: 'Sizes Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'ECG thermal recording media supplied in common clinical Z-fold and roll formats for electrocardiograph machines.',
    features: [
      '50 mm, 80 mm and 210 mm format options',
      'Thermal or chart recorder compatibility',
      'Clean grid calibration'
    ],
    specs: {
      'Common Sizes': '50 mm, 80 mm, 210 mm',
      'Formats': 'Z-fold and rolls',
      'Finish': 'Thermal / clinical chart media'
    },
    applications: [
      'ECG rooms',
      'Emergency departments',
      'Cardiology clinics'
    ],
    packaging: 'Factory-sealed packs; confirm machine model for compatible size.'
  },
  {
    id: 13,
    slug: 'radiation-protection-apparel',
    name: 'Radiation Protection Apparel',
    shortName: 'Lead Aprons & Thyroid Shields',
    category: 'imaging',
    categoryLabel: 'Radiology & Medical Imaging',
    tagline: 'Lead aprons, thyroid shields and lead gloves for radiology staff.',
    image: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    thumbnail: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    badge: 'Radiation Safety',
    leadTime: 'Sizes Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Protective radiology apparel supplied in lead-equivalent options for imaging and interventional staff.',
    features: [
      '0.5 mm Pb lead apron options',
      'Thyroid shields and lead gloves',
      'Adjustable fit'
    ],
    specs: {
      'Lead Equivalence': '0.5 mm Pb options',
      'Types': 'Apron, thyroid shield, gloves',
      'Sizes': 'Adult and custom configurations'
    },
    applications: [
      'X-ray suites',
      'Fluoroscopy',
      'Interventional radiology'
    ],
    packaging: 'Individually packed with size and lead-equivalence labels.'
  },
  {
    id: 14,
    slug: 'led-x-ray-film-viewer',
    name: 'X-Ray Film Viewer (LED)',
    shortName: 'LED X-Ray Film Viewer',
    category: 'imaging',
    categoryLabel: 'Radiology & Medical Imaging',
    tagline: 'Single and double-bank LED illuminators for diagnostic viewing.',
    image: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    thumbnail: 'public/images/catalogue/dry-medical-xray-film-hd.png',
    badge: 'Radiology Equipment',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Bright, uniform LED medical X-ray film illuminators for single and double-bank film viewing.',
    features: [
      'High uniform illumination',
      'Low-energy LED modules',
      'Powder-coated steel housing'
    ],
    specs: {
      'Configuration': 'Single-bank or double-bank',
      'Lighting': 'LED',
      'Surface': 'Easy-clean medical finish'
    },
    applications: [
      'Radiology reporting',
      'Casualty viewing',
      'Clinical film review'
    ],
    packaging: 'Wall-mounted or mobile configuration subject to quotation.'
  },
  {
    id: 15,
    slug: 'pulse-oximeters',
    name: 'Fingertip & Handheld Pulse Oximeters',
    shortName: 'Pulse Oximeters',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Fast adult and pediatric SpO2 and pulse-rate assessment.',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'Portable Monitoring',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'Fingertip and handheld pulse oximeters for screening and spot-check measurement of oxygen saturation and pulse rate.',
    features: [
      'Adult and pediatric finger sensors',
      'Clear digital display',
      'Low-battery and probe indicators'
    ],
    specs: {
      'SpO2': '96% typical clinical range',
      'Sensor': 'Adult and pediatric options',
      'Power': 'Rechargeable or replaceable batteries'
    },
    applications: [
      'Wards',
      'Emergency triage',
      'Community and home care'
    ],
    packaging: 'Device, probe or sensor, carry case and instruction manual.'
  },
  {
    id: 16,
    slug: 'oxygen-delivery-consumables',
    name: 'Oxygen Delivery Consumables',
    shortName: 'Oxygen Masks & Cannulas',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Nasal cannulas, oxygen masks and flowmeters for routine care.',
    image: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    thumbnail: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    badge: 'Respiratory Consumables',
    leadTime: 'Bulk Packs Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Common oxygen delivery accessories for concentrators and cylinder systems across adult and pediatric departments.',
    features: [
      'Adult and pediatric masks',
      'Soft tubing nasal cannulas',
      'Calibrated flowmeters'
    ],
    specs: {
      'Cannulas': 'Adult and pediatric',
      'Masks': 'Simple and standard oxygen masks',
      'Flowmeters': 'Ward-standard connectors'
    },
    applications: [
      'Respiratory wards',
      'Emergency care',
      'Homecare'
    ],
    packaging: 'Available individually or in institutional bulk cartons.'
  },
  {
    id: 17,
    slug: 'compressor-nebulizer-machine',
    name: 'Compressor Nebulizer Machine',
    shortName: 'Compressor Nebulizer',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Heavy-duty clinical and homecare respiratory nebulization.',
    image: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    thumbnail: 'public/images/catalogue/quip-oxygen-concentrator-5l-hd.png',
    badge: 'Respiratory Care',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Oil-free compressor nebulizer systems for reliable aerosol medication delivery in wards and outpatient settings.',
    features: [
      'Compact oil-free compressor',
      'Adult and pediatric kits',
      'Reusable medicine cup'
    ],
    specs: {
      'Technology': 'Piston compressor',
      'Particle Size': 'Medical nebulization range',
      'Voltage': 'AC mains operation'
    },
    applications: [
      'Outpatient respiratory care',
      'Pediatric clinics',
      'Home therapy'
    ],
    packaging: 'Compressor, tubing, masks, mouthpiece and nebulizer cup.'
  },
  {
    id: 18,
    slug: 'portable-suction-machine',
    name: 'Portable Suction Machine',
    shortName: 'Portable Suction Unit',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Single and double-bottle electric surgical suction units.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Critical Care',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Portable electric suction units designed for safe airway clearance in wards, theatres and emergency use.',
    features: [
      'Single or double collection bottle',
      'Overflow protection',
      'Mobile transport unit'
    ],
    specs: {
      'Type': 'Portable electric suction',
      'Bottles': 'Single or double',
      'Use': 'Ward, theatre and emergency'
    },
    applications: [
      'Surgical wards',
      'Emergency rooms',
      'Outpatient procedures'
    ],
    packaging: 'Suction unit, bottles, tubing and reusable/replaceable accessories.'
  },
  {
    id: 19,
    slug: 'infusion-syringe-pumps',
    name: 'Infusion & Syringe Pumps',
    shortName: 'Infusion / Syringe Pumps',
    category: 'critical',
    categoryLabel: 'Critical Care & Patient Monitoring',
    tagline: 'Accurate volumetric infusion and syringe delivery for ward/ICU use.',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'ICU Equipment',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Volumetric infusion and syringe pump options for controlled medication and IV fluid administration.',
    features: [
      'Multiple infusion modes',
      'Alarm indicators',
      'Pole-mountable design'
    ],
    specs: {
      'Types': 'Volumetric and syringe pump',
      'Installation': 'IV pole or rail mount',
      'Modes': 'Common clinical delivery modes'
    },
    applications: [
      'ICU',
      'Theatres',
      'General wards'
    ],
    packaging: 'Pump, power supply, pole clamp and operating manual.'
  },
  {
    id: 20,
    slug: 'sphygmomanometers',
    name: 'Digital & Aneroid Sphygmomanometers',
    shortName: 'BP Monitors',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Upper-arm digital and mercury-free desktop BP units.',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'Primary Care',
    leadTime: 'In Stock - Nairobi Dispatch',
    priceEstimate: 'Request Institutional Quote',
    description: 'Digital and aneroid blood-pressure measurement devices for outpatient and bedside clinical use.',
    features: [
      'Upper-arm and desktop options',
      'Large clinical display',
      'Adult and pediatric cuffs'
    ],
    specs: {
      'Types': 'Digital and aneroid',
      'Cuffs': 'Adult and pediatric',
      'Housing': 'Desktop or portable'
    },
    applications: [
      'Outpatient departments',
      'Wards',
      'Primary care'
    ],
    packaging: 'Device, cuff, hose and carrying pouch where applicable.'
  },
  {
    id: 21,
    slug: 'clinical-stethoscopes',
    name: 'Clinical Stethoscopes',
    shortName: 'Clinical Stethoscopes',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Dual-head adult and pediatric stethoscopes.',
    image: 'public/images/products/ent-diagnostic-set.jpg',
    thumbnail: 'public/images/products/ent-diagnostic-set.jpg',
    badge: 'Consultation Essential',
    leadTime: 'Bulk Packs Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Reliable dual-head stethoscopes for routine adult and pediatric clinical examination.',
    features: [
      'Dual-head chestpiece',
      'Soft-seal ear tips',
      'Adult and pediatric options'
    ],
    specs: {
      'Type': 'Dual-head',
      'Chestpiece': 'Adult and pediatric configurations',
      'Tubing': 'Flexible clinical tubing'
    },
    applications: [
      'General practice',
      'Paediatrics',
      'Community care'
    ],
    packaging: 'Supplied individually or in multi-unit clinical packs.'
  },
  {
    id: 22,
    slug: 'fetal-dopplers-monitors',
    name: 'Fetal Dopplers & Maternal Monitors',
    shortName: 'Fetal Dopplers',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Handheld and desktop fetal heart and maternal monitoring.',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'Maternal Health',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Handheld fetal Dopplers and desktop maternal monitoring systems for antenatal and maternity care.',
    features: [
      'Ultrasonic fetal heart detection',
      'Clear speaker or display',
      'Probe and transducer options'
    ],
    specs: {
      'Modes': 'Handheld Doppler / maternal monitor',
      'Probe': 'Standard obstetric probe',
      'Use': 'Antenatal and maternity care'
    },
    applications: [
      'Maternity clinics',
      'Antenatal units',
      'Midwife-led facilities'
    ],
    packaging: 'Device, probe, gel or accessories and operating manual.'
  },
  {
    id: 23,
    slug: 'infrared-thermometers',
    name: 'Infrared Non-Contact Thermometers',
    shortName: 'Infrared Thermometers',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Clinical forehead thermometers and digital temperature devices.',
    image: 'public/images/products/ent-diagnostic-set.jpg',
    thumbnail: 'public/images/products/ent-diagnostic-set.jpg',
    badge: 'Screening Equipment',
    leadTime: 'Bulk Packs Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Fast clinical thermometers for non-contact forehead screening and conventional digital temperature measurement.',
    features: [
      'Fast temperature reading',
      'Memory or alarm options',
      'Backlit display'
    ],
    specs: {
      'Type': 'Infrared non-contact / digital',
      'Display': 'Digital LCD',
      'Use': 'Forehead or conventional measurement'
    },
    applications: [
      'Hospitals',
      'Clinics',
      'Schools and workplaces'
    ],
    packaging: 'Thermometer, batteries and instruction leaflet.'
  },
  {
    id: 24,
    slug: 'weighing-scales-stadiometers',
    name: 'Weighing Scales & Stadiometers',
    shortName: 'Scales & Stadiometers',
    category: 'outpatient',
    categoryLabel: 'Outpatient & Diagnostics',
    tagline: 'Adult, mechanical, digital and infant weighing solutions.',
    image: 'public/images/catalogue/patient-monitor-hd.png',
    thumbnail: 'public/images/catalogue/patient-monitor-hd.png',
    badge: 'Primary Care',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Mechanical and digital weighing scales, infant scales and stadiometers for clinical growth and assessment programs.',
    features: [
      'Adult and pediatric options',
      'Digital or mechanical display',
      'Stable clinical bases'
    ],
    specs: {
      'Types': 'Adult, infant and height scale',
      'Capacity': 'Patient-type dependent',
      'Display': 'Digital or mechanical'
    },
    applications: [
      'Outpatient clinics',
      'Maternity care',
      'Nutrition programs'
    ],
    packaging: 'Scale with protective packing and calibration/accessory information.'
  },
  {
    id: 25,
    slug: 'examination-surgical-gloves',
    name: 'Examination & Surgical Gloves',
    shortName: 'Medical Gloves',
    category: 'surgical',
    categoryLabel: 'Surgical & Disposables',
    tagline: 'Latex and nitrile gloves in S, M and L sizes.',
    image: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    thumbnail: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    badge: 'Disposable',
    leadTime: 'Bulk Cartons Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Disposable medical gloves for examination and selected surgical applications, available in latex and nitrile.',
    features: [
      'Powdered and powder-free options',
      'Nitrile and latex variants',
      'Sterile and non-sterile choices'
    ],
    specs: {
      'Sizes': 'S, M, L',
      'Material': 'Latex or nitrile',
      'Packing': 'Institutional cartons'
    },
    applications: [
      'Examination',
      'Minor procedures',
      'Surgical supply'
    ],
    packaging: 'Boxes and cartons by size and specification.'
  },
  {
    id: 26,
    slug: 'syringes-cannulas-infusion',
    name: 'Disposable Syringes & IV Cannulas',
    shortName: 'Syringes & IV Cannulas',
    category: 'surgical',
    categoryLabel: 'Surgical & Disposables',
    tagline: '2ml–10ml syringes, 18G–24G cannulas and infusion sets.',
    image: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    thumbnail: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    badge: 'Essential Consumable',
    leadTime: 'Bulk Packs Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Sterile disposable injection and IV administration consumables for hospital and outpatient use.',
    features: [
      'Clear graduated syringes',
      '18G–24G IV cannula options',
      'Infusion set variants'
    ],
    specs: {
      'Syringe Sizes': '2 ml, 5 ml, 10 ml',
      'Cannula Sizes': '18G–24G',
      'Sterility': 'EO or gamma sterile'
    },
    applications: [
      'Nursing',
      'Emergency care',
      'IV therapy'
    ],
    packaging: 'Individual blister or sterile peel packs; bulk cartons.'
  },
  {
    id: 27,
    slug: 'wound-care-dressings',
    name: 'Cotton Wool, Bandages & Plasters',
    shortName: 'Wound Care Consumables',
    category: 'surgical',
    categoryLabel: 'Surgical & Disposables',
    tagline: 'Cotton wool, crepe bandages, zinc oxide and surgical tapes.',
    image: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    thumbnail: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    badge: 'Wound Care',
    leadTime: 'Bulk Packs Available',
    priceEstimate: 'Request Institutional Quote',
    description: 'Routine wound-care supplies for dressing, immobilization and skin protection.',
    features: [
      'Absorbent cotton wool',
      'Crepe and zinc oxide bandages',
      'Surgical and adhesive tapes'
    ],
    specs: {
      'Cotton': 'Approx. 500 g rolls',
      'Bandages': 'Crepe and support sizes',
      'Tapes': 'Zinc oxide and surgical tape'
    },
    applications: [
      'Dressing rooms',
      'Emergency care',
      'Ward supplies'
    ],
    packaging: 'Retail packs or institutional cartons.'
  },
  {
    id: 28,
    slug: 'sterilization-pouches-tape',
    name: 'Sterilization Pouches & Autoclave Tape',
    shortName: 'Sterilization Pouches',
    category: 'surgical',
    categoryLabel: 'Surgical & Disposables',
    tagline: 'Self-sealing reels and indicator tape for instrument sterilization.',
    image: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    thumbnail: 'public/images/products/medex-steri-gauze-absorbent-cotton.jpg',
    badge: 'CSSD Supply',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Self-sealing sterilization pouches and indicator tape for routine autoclave and CSSD workflows.',
    features: [
      'Self-sealing flat reels',
      'Steam indicator options',
      'Visible sterilization indicators'
    ],
    specs: {
      'Formats': 'Flat reels and pouches',
      'Indicator': 'Autoclave-compatible',
      'Closure': 'Self-seal'
    },
    applications: [
      'CSSD',
      'Dental clinics',
      'Surgical preparation'
    ],
    packaging: 'Reels and carton packs in multiple widths.'
  },
  {
    id: 29,
    slug: 'examination-couches',
    name: 'Examination Couches',
    shortName: 'Examination Couch',
    category: 'furniture',
    categoryLabel: 'Hospital Furniture',
    tagline: '2-section padded vinyl clinical exam tables with paper roll holder.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Clinic Furniture',
    leadTime: 'Made / Stocked to Order',
    priceEstimate: 'Request Institutional Quote',
    description: 'Padded two-section examination couches with wipe-clean vinyl upholstery and clinical paper roll support.',
    features: [
      'Two-section padded top',
      'Wipe-clean vinyl cover',
      'Paper roll holder'
    ],
    specs: {
      'Sections': '2',
      'Upholstery': 'Clinical vinyl',
      'Use': 'Examination and minor procedure'
    },
    applications: [
      'Outpatient rooms',
      'Ante-natal clinics',
      'Minor theatre'
    ],
    packaging: 'Flat-pack or assembled dispatch by arrangement.'
  },
  {
    id: 30,
    slug: 'hospital-beds-crank',
    name: 'Hospital Beds (1, 2 & 3 Crank)',
    shortName: 'Hospital Beds',
    category: 'furniture',
    categoryLabel: 'Hospital Furniture',
    tagline: 'ABS-backed 1-, 2- and 3-crank beds with side rails.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Ward Infrastructure',
    leadTime: 'Bulk Institutional Supply',
    priceEstimate: 'Request Institutional Quote',
    description: 'Durable hospital beds configured as 1-crank, 2-crank or 3-crank manual ward units with side rails and mattress.',
    features: [
      'ABS head and foot boards',
      'Collapsible side rails',
      'Waterproof mattress option'
    ],
    specs: {
      'Variants': '1, 2 or 3 crank',
      'Frame': 'Hospital-grade steel',
      'Accessories': 'Side rails and mattress'
    },
    applications: [
      'Medical wards',
      'Surgical wards',
      'Private and public facilities'
    ],
    packaging: 'Supplied per bed with configuration and mattress options.'
  },
  {
    id: 31,
    slug: 'dressing-instrument-trolleys',
    name: 'Dressing & Instrument Trolleys',
    shortName: 'Dressing Trolleys',
    category: 'furniture',
    categoryLabel: 'Hospital Furniture',
    tagline: 'Stainless steel 2-tier and 3-tier ward trolleys.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Stainless Steel',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Stainless-steel dressing and instrument trolleys for ward, theatre and clinical procedure use.',
    features: [
      '2-tier or 3-tier shelves',
      'Guardrails and side handles',
      'Smooth mobile castors'
    ],
    specs: {
      'Material': 'Stainless steel',
      'Layers': '2-tier or 3-tier',
      'Mobility': 'Lockable castors'
    },
    applications: [
      'Wards',
      'Theatres',
      'Dressing rooms'
    ],
    packaging: 'Supplied assembled or semi-assembled.'
  },
  {
    id: 32,
    slug: 'iv-stands-bedside-screens',
    name: 'IV Drip Stands & Bedside Screens',
    shortName: 'IV Stands & Privacy Screens',
    category: 'furniture',
    categoryLabel: 'Hospital Furniture',
    tagline: '4-hook stainless IV stands and 3/4-fold bedside screens.',
    image: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    thumbnail: 'public/images/catalogue/medical-emergency-trolley-hd.png',
    badge: 'Ward Accessory',
    leadTime: 'Available on Request',
    priceEstimate: 'Request Institutional Quote',
    description: 'Mobile IV infusion stands and folding privacy screens for ward and outpatient configurations.',
    features: [
      '4-hook stainless drip stand',
      'Mobile stable base',
      '3-fold and 4-fold screens'
    ],
    specs: {
      'IV Stand': 'Stainless steel 4-hook',
      'Screens': '3-fold or 4-fold',
      'Mobility': 'Smooth casters'
    },
    applications: [
      'Inpatient wards',
      'Outpatient units',
      'Emergency departments'
    ],
    packaging: 'Stand or screen units packed separately or bundled.'
  }
];

// Helper functions for catalog queries
function getAllProducts() {
  return PRODUCTS;
}

function getProductBySlug(slug) {
  return PRODUCTS.find(p => p.slug === slug);
}

function getProductsByCategory(category) {
  if (!category || category === 'all') return PRODUCTS;
  return PRODUCTS.filter(p => p.category === category);
}

function getRelatedProducts(currentSlug, limit = 3) {
  const current = getProductBySlug(currentSlug);
  if (!current) return PRODUCTS.slice(0, limit);
  const sameCat = PRODUCTS.filter(p => p.category === current.category && p.slug !== currentSlug);
  if (sameCat.length >= limit) return sameCat.slice(0, limit);
  const others = PRODUCTS.filter(p => p.slug !== currentSlug && !sameCat.includes(p));
  return [...sameCat, ...others].slice(0, limit);
}
