// Option values retain the workbook's exact categorical representations.
const option = (label, value = label) => ({ label, value });

const counties = [
  'Baringo', 'Bomet', 'Bungoma', 'Busia', 'Elgeyo-Marakwet', 'Embu', 'Garissa',
  'Homabay', 'Isiolo', 'Kajiado', 'Kakamega', 'Kericho', 'Kiambu', 'Kilifi',
  'Kirinyaga', 'Kisii', 'Kisumu', 'Kitui', 'Kwale', 'Laikipia', 'Lamu',
  'Machakos', 'Makueni', 'Mandera', 'Marsabit', 'Meru', 'Migori', 'Mombasa',
  "Murang'a", 'Nairobi City', 'Nakuru', 'Nandi', 'Narok', 'Nyamira',
  'Nyandarua', 'Nyeri', 'Samburu', 'Siaya', 'Taita-Taveta', 'Tana River',
  'Tharaka-Nithi', 'Trans Nzoia', 'Turkana', 'Uasin Gishu', 'Vihiga', 'Wajir',
  'West Pokot',
];

const difficulty = [
  option('No difficulty', 'No- no difficulty'),
  option('Some difficulty', 'Yes - some difficulty'),
  option('A lot of difficulty', 'Yes - a lot of difficulty'),
  option('Cannot do at all'),
];

const sourceToken = option('Source token #NULL! (meaning unresolved)', '#NULL!');
const incomeIndicator = [
  option('Not an income source', '0'),
  option('Is an income source', '1'),
];

export const sections = [
  {
    number: '01',
    title: 'About the respondent',
    description: 'Basic demographic and location information.',
    fields: [
      { name: 'A18', label: 'Age', type: 'age', hint: 'Adults aged 18 or older.' },
      { name: 'Sex', label: 'Sex of selected individual', options: [option('Female'), option('Male')] },
      {
        name: 'A20', label: 'Highest education completed',
        options: [
          option('None', '"None "'),
          option('Some primary', '"Some primary "'),
          option('Primary completed', '"Primary completed"'),
          option('Some secondary', '"Some secondary"'),
          option('Secondary completed', '"Secondary completed "'),
          option('Some technical training', 'Some technical training after secondary school'),
          option('Completed technical training', 'Completed technical training after secondary school'),
          option('Some university', 'Some university'),
          option('University completed', '"University completed "'),
          option('Other', '"Other (Specify) "'),
          option("Don't know", '"Don\'t know (DO NOT READ OUT)"'),
          option('Refused to answer', '"Refused to Answer (DO NOT READ OUT)"'),
          option('Unresolved code 95 (imputed by model)', '95'),
        ],
      },
      { name: 'county', label: 'County', options: counties.map((name) => option(name)) },
      { name: 'A08', label: 'Cluster type', options: [option('Rural'), option('Urban')] },
    ],
  },
  {
    number: '02',
    title: 'Livelihood & identification',
    description: 'Income sources refer to the past 12 months.',
    fields: [
      { name: 'B3A__2', label: 'Employment income source', options: incomeIndicator, hint: 'Whether income was received from employment in the past 12 months (0=No, 1=Yes).' },
      { name: 'B3A__4', label: 'Own-business income source', options: incomeIndicator, hint: 'Whether income was received from running own business/self-employment in the past 12 months (0=No, 1=Yes).' },
      { name: 'B3Ii', label: 'Total income last month', type: 'income', hint: 'In Kenyan shillings.' },
      { name: 'ID_card', label: 'Identification document', options: [
        option('Has ID (national ID, passport or alien ID)', 'Has ID (National Identity Card (ID),Passport,Alien ID)'),
        option('No ID'),
      ] },
    ],
  },
  {
    number: '03',
    title: 'Digital access',
    description: 'General phone and internet access, not financial transactions.',
    fields: [
      { name: 'S1', label: 'Phone ownership and use', options: [
        option('Owns a phone for personal use', 'I own a mobile that only I use/Nina simu ambayo ni mimi tu ninaitumia'),
        option('Owns a phone shared with others', 'I own a mobile phone that both me and others use/Nina simu ya mkononi ambayo mim'),
        option('Uses someone else’s phone regularly', 'I don\u00e2\u20ac\u2122t own a mobile phone but am able to use someone else\u00e2\u20ac\u2122s phone regularly'),
        option('Does not own or use a phone', 'I don\u00e2\u20ac\u2122t own or use a mobile phone/Sina wala situmii simu ya mkononi'),
        option('Refused to answer', 'Refused to Answer (DO NOT READ OUT)/Kataa kujibu'),
        sourceToken,
      ] },
      { name: 'S3', label: 'Internet use frequency', options: [
        option('Daily', 'Daily/"Kila siku"'),
        option('Weekly', 'Weekly/Kila wiki"'),
        option('Monthly', 'Monthly/Mara moja kwa mwezi"'),
        option('Less often', 'Less ofteN/Mara kwa mara"'),
        option('Never', 'Never/Situmii"'),
        option('Refused to answer', 'Refused to Answer/Kataa kujibu'),
        sourceToken,
      ] },
    ],
  },
  {
    number: '04',
    title: 'Functional difficulties',
    description: 'Choose the response that best describes each activity.',
    fields: [
      { name: 'A24i', label: 'Seeing', options: [...difficulty, sourceToken] },
      { name: 'A24ii', label: 'Hearing', options: [...difficulty, sourceToken] },
      { name: 'A24iii', label: 'Walking or climbing', options: [...difficulty, sourceToken] },
      { name: 'A24iv', label: 'Remembering or concentrating', options: difficulty },
      { name: 'A24v', label: 'Self-care', options: [...difficulty, sourceToken] },
      { name: 'A24vi', label: 'Communicating', options: [...difficulty, sourceToken] },
    ],
  },
];

export const fields = sections.flatMap((section) => section.fields);
export const MISSING = '__missing__';

export function prepareRequest(values, incomeMissing) {
  const errors = {};
  const payload = {};
  for (const field of fields) {
    const value = values[field.name] ?? '';
    if (field.type === 'age') {
      const age = Number(value);
      if (!/^\d+$/.test(value) || !Number.isSafeInteger(age) || age < 18 || age === 98 || age === 99) {
        errors[field.name] = 'Enter an adult age (18+).';
      } else {
        payload[field.name] = age;
      }
    } else if (field.type === 'income') {
      if (incomeMissing) {
        payload[field.name] = null;
      } else if (value.trim() === '' || !Number.isFinite(Number(value)) || Number(value) < 0) {
        errors[field.name] = 'Enter a non-negative income or select income unavailable.';
      } else {
        payload[field.name] = Number(value);
      }
    } else if (value === '') {
      errors[field.name] = 'Select a response, including unavailable if needed.';
    } else if (value === MISSING) {
      payload[field.name] = null;
    } else if (!field.options.some((entry) => entry.value === value)) {
      errors[field.name] = 'Select a valid response.';
    } else {
      payload[field.name] = field.name === 'B3A__2' || field.name === 'B3A__4'
        ? Number(value)
        : value;
    }
  }
  return { errors, payload };
}

export function getFieldLabel(fieldName) {
  const field = fields.find(f => f.name === fieldName);
  return field ? field.label : fieldName;
}
