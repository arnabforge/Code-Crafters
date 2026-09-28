import React,{useState} from "react";
import {Row,Col,Card,Badge,Form,Button,Spinner,Alert} from "react-bootstrap";
import {FaLocationDot,FaPlugCircleBolt} from "react-icons/fa6";
import {api} from "../api";
import PlaceAutocomplete from "./PlaceAutocomplete";

export default function Stations(){
 const [place,setPlace]=useState(""); const [coords,setCoords]=useState(null); const [stations,setStations]=useState([]); const [loading,setLoading]=useState(false); const [error,setError]=useState("");
 const search=async e=>{e?.preventDefault(); if(!coords){setError("Choose a suggested place first so the charger search has coordinates.");return;} setLoading(true);setError("");try{const x=await api(`/api/stations?lat=${coords.lat}&lng=${coords.lng}&distance_km=30`);setStations(x.stations||[]);if(!x.live)setError(x.message)}catch(err){setError(err.message)}finally{setLoading(false)}};
 return <div className="page"><div className="mb-3"><h2>Charging Stations</h2><p className="text-secondary">Search any real place, then inspect nearby charger details, connector information, pricing and a clearly labelled simulated queue/wait.</p></div>
 <Card className="shadow-sm border-0 mb-4"><Card.Body><Form onSubmit={search}><Row className="g-3 align-items-end"><Col lg={9}><PlaceAutocomplete label="Search near" value={place} onChange={setPlace} onSelect={setCoords} placeholder="Search a city, address, landmark or business"/></Col><Col lg={3}><Button size="lg" className="w-100" disabled={loading||!coords}>{loading?<Spinner size="sm"/>:<><FaLocationDot className="me-2"/>Find chargers</>}</Button></Col></Row></Form></Card.Body></Card>
 {error&&<Alert variant="warning">{error}</Alert>}
 <Row className="g-3">{stations.map(s=><Col md={6} xl={4} key={s.id}><Card className="station-card shadow-sm border-0 h-100"><Card.Body><Badge bg={s.status_is_operational===false?"danger":"success"}>{s.status}</Badge><h5 className="mt-2">{s.name}</h5><div className="text-secondary small">{s.address||"Address not reported"}</div><hr/><div><b>Operator:</b> {s.operator}</div><div><b>Usage / pricing:</b> {s.usage_cost||s.usage||"Not reported"}</div><div><b><FaPlugCircleBolt className="me-1"/>Ports:</b> {s.ports?.map(p=>`${p.type}${p.power_kw?` (${p.power_kw} kW)`:""}`).join(", ")||"Not reported"}</div><div className="mt-2"><b>Queue simulation:</b> {s.queue??"—"} vehicles · {s.estimated_wait_min??"—"} min</div>{s.ocm_url&&<a className="small" href={s.ocm_url} target="_blank" rel="noreferrer">Open Charge Map record ↗</a>}{s.google_maps_url&&<a className="small d-block" href={s.google_maps_url} target="_blank" rel="noreferrer">Open Google Maps ↗</a>}</Card.Body></Card></Col>)}</Row>
 {coords&&stations.length===0&&!loading&&!error&&<Alert variant="info">No charger records were returned for this search area.</Alert>}
 </div>
}
