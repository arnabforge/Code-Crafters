import React, {useEffect, useRef, useState} from "react";
import {Form, Spinner} from "react-bootstrap";
import {api} from "../api";

export default function PlaceAutocomplete({label, value, onChange, onSelect, placeholder, required=true}) {
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);
  const requestId = useRef(0);

  useEffect(() => () => clearTimeout(timer.current), []);

  const handleChange = (next) => {
    onChange(next);
    clearTimeout(timer.current);
    setSuggestions([]);
    if (next.trim().length < 2) { setOpen(false); return; }
    timer.current = setTimeout(async () => {
      const id = ++requestId.current;
      setLoading(true);
      try {
        const data = await api(`/api/places/autocomplete?input=${encodeURIComponent(next.trim())}`);
        if (id === requestId.current) { setSuggestions(data.suggestions || []); setOpen(true); }
      } catch {
        if (id === requestId.current) { setSuggestions([]); setOpen(false); }
      } finally { if (id === requestId.current) setLoading(false); }
    }, 280);
  };

  const choose = async (item) => {
    setOpen(false);
    onChange(item.text);
    if (!item.place_id) return;
    try {
      const details = await api(`/api/places/${encodeURIComponent(item.place_id)}`);
      onChange(details.formatted || item.text);
      onSelect?.(details);
    } catch {
      onSelect?.({place_id: item.place_id, formatted: item.text});
    }
  };

  return <div className="place-autocomplete">
    <Form.Label>{label}</Form.Label>
    <div className="position-relative">
      <Form.Control size="lg" required={required} value={value} onChange={e=>handleChange(e.target.value)} onFocus={()=>suggestions.length&&setOpen(true)} onBlur={()=>setTimeout(()=>setOpen(false),180)} placeholder={placeholder}/>
      {loading && <Spinner animation="border" size="sm" className="place-spinner"/>}
      {open && suggestions.length > 0 && <div className="suggestion-menu" role="listbox">
        {suggestions.map((s, i)=><button type="button" className="suggestion-item" key={`${s.place_id}-${i}`} onMouseDown={e=>e.preventDefault()} onClick={()=>choose(s)}>
          <span className="suggestion-pin">⌖</span>
          <span><strong>{s.main_text}</strong><small>{s.secondary_text || s.text}</small></span>
        </button>)}
      </div>}
    </div>
    <Form.Text>Start typing a real address, place, landmark or business. Suggestions come from Google Places.</Form.Text>
  </div>;
}
