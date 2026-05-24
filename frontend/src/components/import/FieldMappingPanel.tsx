const fields = ["domain", "ip", "email", "phone", "username", "url", "hash", "source", "confidence"];

export default function FieldMappingPanel({ columns }: { columns: string[] }) {
  return <section className="field-mapping"><header><strong>Suggested Mapping</strong><span>UI preview only until backend importer is available</span></header>{columns.map((column) => <label key={column}><span>{column}</span><select defaultValue={fields.find((field) => column.toLowerCase().includes(field)) || "ignore"}><option value="ignore">Ignore</option>{fields.map((field) => <option value={field} key={field}>{field}</option>)}</select></label>)}</section>;
}

