const media = [
  'courtyard',
  'coastal',
  'garden',
  'sunroom',
  'terrace',
  'cottage',
];
export function mediaFor(id: string) {
  const hash = [...id].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return `/media/${media[hash % media.length]}.svg`;
}
