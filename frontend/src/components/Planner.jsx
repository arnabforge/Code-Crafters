import React,{useState} from "react";
import {Form,Button,Row,Col,Card,Badge,Alert,Table,Spinner} from "react-bootstrap";
import {FaBolt,FaClock,FaRoute,FaCarSide,FaLocationDot} from "react-icons/fa6";
import {api} from "../api";
import MapView from "./MapView";
import PlaceAutocomplete from "./PlaceAutocomplete";

export default function Planner({profile,vehicles,premium,ownerId}){
 const [source,setSource]=useState("");
 const [destination,setDestination]=useState("");
 const [result,setResult]=useState(null);
 const [loading,setLoading]=useState(false);
 const [error,setError]=useState("");
 const analyze=async e=>{
  e.preventDefault();
  if(!profile.vehicle){setError("Save an owner and vehicle profile before planning a route.");return;}
  setLoading(true);setError("");
  try{setResult(await api("/api/plan",{method:"POST",body:JSON.stringify({owner_id:ownerId,source,destination,vehicle_id:profile.vehicle,battery_pct:Number(profile.charge),personal_range_km:profile.personalRange?Number(profile.personalRange):null,subscription:premium?"premium":"free"})}))}
  catch(err){setError(err.message)}finally{setLoading(false)}
 };
 const v=vehicles[profile.vehicle];
 return <div className="page">
  <div className="d-flex flex-wrap justify-content-between align-items-end mb-3"><div><h2>Personalized Route Planner</h2><p className="text-secondary mb-0">Real road routing, Google-style place search and vehicle-aware charging decisions.</p></div>{result&&<Badge bg={result.decision==="DIRECT"?"success":result.decision==="CHARGE"?"primary":"danger"} className="decision-badge">{result.decision}</Badge>}</div>
  {!ownerId && <Alert variant="info"><FaCarSide className="me-2"/>Save your owner + vehicle profile on Dashboard first. The planner uses that profile's battery and range estimate.</Alert>}
  <Card className="shadow-sm border-0 mb-4"><Card.Body className="p-4"><Form onSubmit={analyze}><Row className="g-3 align-items-end">
   <Col lg={5}><PlaceAutocomplete label="From" value={source} onChange={setSource} placeholder="Search an address or place"/></Col>
   <Col lg={5}><PlaceAutocomplete label="To" value={destination} onChange={setDestination} placeholder="Search your destination"/></Col>
   <Col lg={2}><Form.Label>Battery</Form.Label><Form.Control size="lg" value={`${profile.charge ?? 0}%`} readOnly/><Form.Text>Change on Dashboard.</Form.Text></Col>
   <Col><Button size="lg" type="submit" disabled={loading||!ownerId||!source.trim()||!destination.trim()}>{loading?<><Spinner size="sm" className="me-2"/>Calculating real route…</>:<><FaRoute className="me-2"/>Plan my EV journey</>}</Button></Col>
  </Row></Form></Card.Body></Card>
  {error&&<Alert variant="danger">{error}</Alert>}
  {result&&<>
   <Row className="g-3 mb-4"><Metric icon={<FaRoute/>} label="Real road distance" value={`${result.distance_km} km`}/><Metric icon={<FaBolt/>} label="Safe range available" value={`${result.available_range_km} km`}/><Metric icon={<FaCarSide/>} label="Current battery" value={`${result.battery_pct}%`}/><Metric icon={<FaClock/>} label="Route time" value={`${result.duration_min} min`}/></Row>
   <Alert variant={result.decision==="DIRECT"?"success":result.decision==="CHARGE"?"primary":"warning"}><strong>{result.message}</strong><br/><small>{result.vehicle.range_blend_source}. {result.queue_note}</small></Alert>
   <MapView result={result}/>
   {result.recommended_station&&<Recommendation station={result.recommended_station} premium={premium}/>} 
   <Card className="shadow-sm border-0 mt-4"><Card.Body><div className="d-flex justify-content-between flex-wrap gap-2"><h5><FaLocationDot className="me-2"/>Charging candidates</h5><small className="text-secondary">Provider data + real road legs + simulated queue</small></div><div className="table-responsive"><Table hover className="mt-3 align-middle"><thead><tr><th>Station / operator</th><th>Road leg</th><th>Ports</th><th>Status</th><th>Queue</th><th>Waiting time</th><th>Charge / Pricing</th><th>Extra time</th></tr></thead><tbody>{result.stations.map(s=><tr key={s.id}><td><strong>{s.name}</strong><br/><small>{s.operator||"Not reported"}</small></td><td><div>{s.distance_from_source_km ?? "—"} km <small className="d-block text-secondary">source → station</small></div><div className="mt-1">{s.station_to_destination_km ?? "—"} km <small className="d-block text-secondary">station → destination</small></div></td><td>{s.ports?.slice(0,3).map(p=>`${p.type}${p.power_kw?` (${p.power_kw} kW)`:""}`).join(", ")||"Not reported"}</td><td><Badge bg={s.status_is_operational===false?"danger":s.status_is_operational===true?"success":"secondary"}>{s.status||"Not reported"}</Badge></td><td><strong>{s.queue ?? "—"}</strong> vehicles</td><td>{s.estimated_wait_min!=null?`${s.estimated_wait_min} min`:"—"}</td><td>{s.estimated_charge_min!=null?<><strong>{s.estimated_charge_min} min</strong><br/></>:null}<small>{s.usage_cost||"Pricing not reported"}</small></td><td>{s.total_extra_min!=null?`${s.total_extra_min} min`:"—"}</td></tr>)}</tbody></Table></div></Card.Body></Card>
  </>}
 </div>
}
function Metric({icon,label,value}){return <Col sm={6} lg={3}><div className="metric"><span className="metric-icon">{icon}</span><small>{label}</small><strong>{value}</strong></div></Col>}
function Recommendation({station,premium}){return <Card className="recommendation shadow-sm border-0 mt-4"><Card.Body className="p-4"><Badge bg="primary">{premium?"Premium time optimizer":"Reachable charging stop"}</Badge><h3 className="mt-2">{station.name}</h3><p className="text-secondary">{station.address||"Address not reported"} · {station.operator}</p><Row className="g-3"><Col md={3}><b>{station.distance_from_source_km} km</b><small>road distance from source</small></Col><Col md={3}><b>{station.queue}</b><small>simulated queue</small></Col><Col md={3}><b>{station.estimated_wait_min} min</b><small>simulated wait</small></Col><Col md={3}><b>{station.estimated_charge_min} min</b><small>estimated charging</small></Col></Row></Card.Body></Card>}
