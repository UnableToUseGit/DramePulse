export interface StoryQaPanelState {
  isOpen: boolean;
  question: string;
  answer?: string;
  error?: string;
  isLoading: boolean;
}

export function createInitialStoryQaState(): StoryQaPanelState {
  return {
    isOpen: false,
    question: "",
    answer: undefined,
    error: undefined,
    isLoading: false
  };
}

export function resetStoryQaState(): StoryQaPanelState {
  return createInitialStoryQaState();
}
