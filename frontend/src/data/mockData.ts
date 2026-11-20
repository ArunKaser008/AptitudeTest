export type AssessmentQuestion = {
  id: number;
  section?: string;
  topic: string;
  difficulty: "Easy" | "Medium" | "Hard";
  prompt: string;
  options: string[];
  answer: number;
  explanation: string;
};

export type AssessmentDefinition = {
  id: string;
  title: string;
  description: string;
  questions: number;
  previewQuestionCount: number;
  durationMinutes: number;
  duration: string;
  level: string;
  sections: string[];
  previewDistribution: Record<string, number>;
  badge: string;
};

export type TopicScore = {
  name: string;
  score: number;
  color: string;
};

export const isDemoData = true;

export const overview = {
  readiness: 68,
  testsCompleted: 8,
  accuracy: 76,
  avgSpeed: "52 sec",
  practiceTime: "12h 40m",
  improvement: 12,
};

export const sectionScores: TopicScore[] = [
  { name: "Quantitative", score: 76, color: "#1a8fc4" },
  { name: "Logical reasoning", score: 62, color: "#48a9d1" },
  { name: "Verbal ability", score: 81, color: "#52b788" },
  { name: "Data interpretation", score: 58, color: "#f0a64b" },
  { name: "Problem solving", score: 70, color: "#7b78d2" },
];

export const performanceTrend = [
  { date: "Oct 2", score: 49, accuracy: 55 },
  { date: "Oct 9", score: 54, accuracy: 61 },
  { date: "Oct 16", score: 57, accuracy: 65 },
  { date: "Oct 23", score: 61, accuracy: 69 },
  { date: "Oct 30", score: 68, accuracy: 76 },
];

export const recommendations = [
  {
    title: "Time and Work",
    detail: "Build speed with a focused 10-question practice set.",
    meta: "Quantitative · 15 min",
    tone: "blue",
  },
  {
    title: "Data Interpretation",
    detail: "Review table-based questions and percentage change.",
    meta: "Data interpretation · 20 min",
    tone: "amber",
  },
  {
    title: "Seating Arrangements",
    detail: "Strengthen accuracy with linear arrangement puzzles.",
    meta: "Logical reasoning · 15 min",
    tone: "purple",
  },
];

export const assessments: AssessmentDefinition[] = [
  {
    id: "foundation",
    title: "Foundation Aptitude Test",
    description: "Build a baseline across the core placement aptitude skills.",
    questions: 60,
    previewQuestionCount: 10,
    durationMinutes: 60,
    duration: "60 min",
    level: "All levels",
    sections: ["Quantitative", "Logical reasoning", "Verbal", "Data interpretation", "Problem solving"],
    previewDistribution: {
      Quantitative: 2,
      "Logical reasoning": 2,
      Verbal: 2,
      "Data interpretation": 2,
      "Analytical problem solving": 2,
    },
    badge: "Recommended",
  },
  {
    id: "advanced",
    title: "Advanced Placement Assessment",
    description: "Challenge yourself with advanced reasoning and programming logic.",
    questions: 60,
    previewQuestionCount: 10,
    durationMinutes: 90,
    duration: "90 min",
    level: "Intermediate",
    sections: [
      "Advanced quantitative",
      "Advanced reasoning",
      "Advanced verbal",
      "Pseudocode",
      "Programming logic",
      "Debugging and complexity",
    ],
    previewDistribution: {
      "Advanced quantitative": 2,
      "Advanced reasoning": 2,
      "Advanced verbal": 1,
      Pseudocode: 2,
      "Programming logic": 2,
      "Debugging and complexity": 1,
    },
    badge: "Advanced",
  },
  {
    id: "company",
    title: "Company-style Mock Test",
    description: "Practise with a MentorMuni simulation inspired by public hiring patterns.",
    questions: 30,
    previewQuestionCount: 10,
    durationMinutes: 45,
    duration: "45 min",
    level: "All levels",
    sections: ["Quantitative", "Logical reasoning", "Verbal", "Data interpretation"],
    previewDistribution: {
      Quantitative: 3,
      "Logical reasoning": 3,
      Verbal: 2,
      "Data interpretation": 2,
    },
    badge: "Practice simulation",
  },
];

export const companies = [
  { name: "TCS", category: "IT services", tests: 3, color: "blue" },
  { name: "Infosys", category: "IT services", tests: 2, color: "purple" },
  { name: "Accenture", category: "Consulting & technology", tests: 2, color: "blue" },
  { name: "Wipro", category: "IT services", tests: 1, color: "amber" },
];

export const questions: AssessmentQuestion[] = [
  {
    id: 1,
    topic: "Percentages",
    difficulty: "Easy",
    prompt: "A value increases from 80 to 100. What is the percentage increase?",
    options: ["20%", "25%", "30%", "125%"],
    answer: 1,
    explanation: "The increase is 20. Divide by the original value: 20 ÷ 80 × 100 = 25%.",
  },
  {
    id: 2,
    topic: "Time and Work",
    difficulty: "Medium",
    prompt: "A team completes a task in 12 days. At the same rate, how much is completed in 3 days?",
    options: ["1/2", "1/3", "1/4", "1/6"],
    answer: 2,
    explanation: "Three days is one quarter of 12 days, so one quarter of the task is completed.",
  },
  {
    id: 3,
    topic: "Number Series",
    difficulty: "Easy",
    prompt: "Choose the next number in the series: 3, 7, 15, 31, __",
    options: ["47", "55", "63", "64"],
    answer: 2,
    explanation: "Each term is doubled and then increased by one: 31 × 2 + 1 = 63.",
  },
  {
    id: 4,
    topic: "Data Interpretation",
    difficulty: "Hard",
    prompt: "A store's quarterly sales rise from $80,000 to $92,000. What is the percentage increase?",
    options: ["12%", "15%", "18%", "20%"],
    answer: 1,
    explanation: "The increase is $12,000. Divide by the original sales: 12,000 ÷ 80,000 × 100 = 15%.",
  },
  {
    id: 5,
    topic: "Ratio and Proportion",
    difficulty: "Easy",
    prompt: "The ratio of red to blue pens is 2:3. If there are 25 pens, how many are blue?",
    options: ["10", "12", "15", "18"],
    answer: 2,
    explanation: "There are 5 equal parts in total. Each part is 25 ÷ 5 = 5, so blue pens are 3 × 5 = 15.",
  },
  {
    id: 6,
    topic: "Averages",
    difficulty: "Easy",
    prompt: "What is the average of 12, 16, 20, and 24?",
    options: ["16", "18", "20", "22"],
    answer: 1,
    explanation: "Add the values and divide by four: (12 + 16 + 20 + 24) ÷ 4 = 18.",
  },
  {
    id: 7,
    topic: "Profit and Loss",
    difficulty: "Medium",
    prompt: "An item bought for ₹500 is sold for ₹575. What is the profit percentage?",
    options: ["12%", "15%", "17.5%", "20%"],
    answer: 1,
    explanation: "Profit is ₹75. The profit percentage is 75 ÷ 500 × 100 = 15%.",
  },
  {
    id: 8,
    topic: "Speed, Time and Distance",
    difficulty: "Medium",
    prompt: "A car travels 150 km in 3 hours. What is its average speed?",
    options: ["45 km/h", "50 km/h", "55 km/h", "60 km/h"],
    answer: 1,
    explanation: "Average speed equals distance divided by time: 150 ÷ 3 = 50 km/h.",
  },
  {
    id: 9,
    topic: "Number Systems",
    difficulty: "Easy",
    prompt: "What is the smallest positive number divisible by both 6 and 8?",
    options: ["12", "18", "24", "48"],
    answer: 2,
    explanation: "The least common multiple of 6 and 8 is 24.",
  },
  {
    id: 10,
    topic: "Probability",
    difficulty: "Medium",
    prompt: "A fair six-sided die is rolled once. What is the probability of rolling an even number?",
    options: ["1/6", "1/3", "1/2", "2/3"],
    answer: 2,
    explanation: "Three of the six outcomes (2, 4, 6) are even, so the probability is 3/6 = 1/2.",
  },
  {
    id: 11,
    topic: "Coding and Decoding",
    difficulty: "Easy",
    prompt: "If each letter is replaced by the next letter in the alphabet, how is CODE written?",
    options: ["DPEF", "BNCD", "DPED", "EPEF"],
    answer: 0,
    explanation: "Move each letter forward by one: C→D, O→P, D→E, E→F.",
  },
  {
    id: 12,
    topic: "Direction Sense",
    difficulty: "Easy",
    prompt: "Mira walks 4 km north, then 3 km east. How far is she from her starting point?",
    options: ["5 km", "6 km", "7 km", "12 km"],
    answer: 0,
    explanation: "The path forms a right triangle. The straight-line distance is √(4² + 3²) = 5 km.",
  },
  {
    id: 13,
    topic: "Grammar",
    difficulty: "Easy",
    prompt: "Choose the grammatically correct sentence.",
    options: ["Each of the applicants have arrived.", "Each of the applicants has arrived.", "Each applicants has arrived.", "Each of applicants have arrived."],
    answer: 1,
    explanation: "'Each' is singular, so it takes the singular verb 'has'.",
  },
  {
    id: 14,
    topic: "Vocabulary",
    difficulty: "Medium",
    prompt: "Choose the word closest in meaning to 'concise'.",
    options: ["Brief", "Unclear", "Detailed", "Delayed"],
    answer: 0,
    explanation: "'Concise' means brief and expressed clearly using few words.",
  },
  {
    id: 15,
    topic: "Simple Interest",
    difficulty: "Medium",
    prompt: "What simple interest is earned on ₹2,000 at 5% per year for 2 years?",
    options: ["₹100", "₹150", "₹200", "₹250"],
    answer: 2,
    explanation: "Simple interest is principal × rate × time ÷ 100: 2,000 × 5 × 2 ÷ 100 = ₹200.",
  },
  {
    id: 16,
    topic: "Time and Work",
    difficulty: "Medium",
    prompt: "A worker completes one task in 8 days. What fraction of the task is completed in 2 days at a steady rate?",
    options: ["1/2", "1/3", "1/4", "1/8"],
    answer: 2,
    explanation: "Two days is one quarter of 8 days, so one quarter of the task is completed.",
  },
  {
    id: 17,
    topic: "Data Interpretation",
    difficulty: "Hard",
    prompt: "A team resolves 48 tickets on Monday and 60 on Tuesday. By what percentage did resolutions increase?",
    options: ["20%", "25%", "30%", "12%"],
    answer: 1,
    explanation: "The increase is 12 tickets. Relative to Monday: 12 ÷ 48 × 100 = 25%.",
  },
  {
    id: 18,
    topic: "Number Series",
    difficulty: "Medium",
    prompt: "Choose the next number: 2, 6, 12, 20, 30, __",
    options: ["36", "40", "42", "44"],
    answer: 2,
    explanation: "The differences are 4, 6, 8, and 10. The next difference is 12, giving 42.",
  },
  {
    id: 19,
    topic: "Sentence Correction",
    difficulty: "Medium",
    prompt: "Choose the best correction: 'She is working here since 2023.'",
    options: ["She works here since 2023.", "She has been working here since 2023.", "She was working here since 2023.", "She is worked here since 2023."],
    answer: 1,
    explanation: "Use the present perfect continuous with 'since' to describe an action that began in the past and continues now.",
  },
  {
    id: 20,
    topic: "Ratio and Proportion",
    difficulty: "Hard",
    prompt: "A recipe uses flour and sugar in a 5:2 ratio. If 350 g of flour is used, how much sugar is needed?",
    options: ["100 g", "120 g", "140 g", "175 g"],
    answer: 2,
    explanation: "Each ratio part is 350 ÷ 5 = 70 g. Sugar is 2 parts, or 140 g.",
  },
];
