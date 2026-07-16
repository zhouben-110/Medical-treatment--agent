interface Props {
  symptoms: string[];
  onRemoveSymptom?: (symptom: string) => void;
}

function parseSymptom(raw: string): string {
  try {
    const obj = JSON.parse(raw);
    return obj.symptom || raw;
  } catch {
    return raw;
  }
}

export default function SymptomTags({ symptoms, onRemoveSymptom }: Props) {
  if (!symptoms.length) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4 items-center">
      <span className="text-xs text-gray-500 dark:text-gray-400">已识别症状：</span>
      {symptoms.map((symptom, index) => (
        <span
          key={index}
          className="inline-flex items-center gap-1.5 px-3 py-1 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border border-blue-200 dark:border-blue-800 rounded-full text-xs font-medium"
        >
          {parseSymptom(symptom)}
          {onRemoveSymptom && (
            <button
              onClick={() => onRemoveSymptom(symptom)}
              className="w-3.5 h-3.5 inline-flex items-center justify-center rounded-full hover:bg-blue-200/50 dark:hover:bg-blue-950 text-blue-500 hover:text-blue-700 dark:hover:text-blue-100 transition font-bold"
              title="更正/删除此症状"
            >
              &times;
            </button>
          )}
        </span>
      ))}
    </div>
  );
}
