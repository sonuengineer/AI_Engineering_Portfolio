export type Difficulty = "beginner" | "intermediate" | "advanced" | "senior";
export const DIFFICULTIES: Difficulty[] = ["beginner", "intermediate", "advanced", "senior"];

export interface Question {
  id: string;
  topic: string;
  difficulty: Difficulty;
  question: string;
  answer: string;
  reasoning?: string;
  code_refs: string[];
  follow_ups: string[];
  kind: "implemented" | "proposed_extension";
}
export interface Exercise {
  id: string; title: string; difficulty: Difficulty; prompt: string; solution_outline: string; evaluation_criteria: string[];
}
export interface Walkthrough { title: string; steps: string[] }
export interface MockInterview { title: string; level: Difficulty; question_ids: string[] }
export interface Handbook {
  project: string;
  title: string;
  generated_from: string;
  topics: { id: string; title: string }[];
  questions: Question[];
  exercises: Exercise[];
  walkthroughs: Walkthrough[];
  mock_interviews: MockInterview[];
}
