import React from "react";

export default function MaterialExpansion({value="", approved=false, sourceHash="", onChange, onExpand, disabled=false, canExpand=false}) {
  const stale=!!value && !sourceHash;
  return <section aria-label="Optional material expansion">
    <h3>Expand this material (optional)</h3>
    <p>Add missing explanations and a worked example using model knowledge. Review the additions for accuracy and scope before using them. This does not search the internet.</p>
    <button type="button" disabled={disabled || !canExpand} onClick={onExpand}>{value ? "Generate a new expansion" : "Expand this material"}</button>
    {value && <>
      <label>AI-drafted additions<textarea rows={10} maxLength={12000} disabled={disabled} value={value} onChange={e=>onChange({materialExpansion:e.target.value,expansionApproved:false})}/></label>
      {stale && <p role="status">The materials or learning scope changed. Generate a new expansion or remove these additions.</p>}
      <label><input type="checkbox" disabled={disabled || stale} checked={approved} onChange={e=>onChange({expansionApproved:e.target.checked})}/>I reviewed these additions for accuracy and scope</label>
      <button type="button" disabled={disabled} onClick={()=>onChange({materialExpansion:"",expansionApproved:false,expansionSourceHash:""})}>Remove additions</button>
    </>}
  </section>;
}
