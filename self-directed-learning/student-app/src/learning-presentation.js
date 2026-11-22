// Translate only the server's known instruction envelopes. Unknown tutor prose,
// feedback, hints and follow-up questions remain intact in conversation history.
export function presentTutorMessage(
  content,
  { activeQuestion, scenario } = {},
) {
  const questions = [];
  const completion = content.match(
    /^Application and interview feedback: ([\s\S]+?)\n\nIntended outcome: ([\s\S]+)\n\nLesson complete\. (Completion records participation; feedback describes the evidence of understanding\.)$/,
  );
  if (completion) {
    const [, feedback, outcomes, note] = completion;
    return {
      text: feedback.trim(),
      questions,
      completion: { outcomes: uniqueContent(outcomes.split("\n")), note },
    };
  }
  let text = content;
  if (scenario?.trim())
    text = text.replace(`Scenario: ${scenario.trim()}\n\n`, "");
  text = text.replace(
    /(?:Application part (\d+) of (\d+) — ([^\n]+)\n\n([\s\S]*?)\n\nA couple of sentences or bullets is enough\.|Interview question (\d+) of (\d+)\n\n([\s\S]*?)\n\nOne or two sentences is enough\.)/g,
    (
      envelope,
      part,
      count,
      title,
      prompt,
      interview,
      interviewCount,
      interviewPrompt,
    ) => {
      const question = {
        title: title || `Interview question ${interview}`,
        prompt: prompt || interviewPrompt,
      };
      if (question.prompt.trim() !== activeQuestion?.prompt?.trim())
        questions.push(question);
      return "";
    },
  );
  return { text: text.trim(), questions };
}

export function uniqueContent(values) {
  return [...new Set(values.map((value) => value?.trim()).filter(Boolean))];
}

// This is a generated fallback marker, not an authored reading or external link.
// Resolve it to the actual assignment downloads instead of displaying its metadata.
export function isCourseMaterialPlaceholder(resource) {
  return !resource.url && resource.title === "Selected course materials" &&
    resource.provider === "Instructor course materials";
}
