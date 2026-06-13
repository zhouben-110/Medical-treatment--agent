interface Props {
  symptoms: string[];
}

function parseSymptom(raw: string): string {
  try {
    const obj = JSON.parse(raw);
    return obj.symptom || raw;
  } catch {
    return raw;
  }
}

export default function SymptomTags({ symptoms }: Props) {
  if (!symptoms.length) return null;

  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {symptoms.map((symptom, index) => (
        <span
          key={index}
          className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm"
        >
          {parseSymptom(symptom)}
        </span>
      ))}
    </div>
  );
}
