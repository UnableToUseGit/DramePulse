import { resetStoryQaState } from "../storyQaState";

describe("storyQaState", () => {
  it("resets panel state when switching videos", () => {
    expect(resetStoryQaState()).toEqual({
      isOpen: false,
      question: "",
      answer: undefined,
      error: undefined,
      isLoading: false
    });
  });
});
