import React,{useState} from "react";
import {Card,Row,Col,Form,Button,Alert,Badge,InputGroup} from "react-bootstrap";
import {FaCar,FaBolt,FaRoute,FaGaugeHigh,FaDatabase} from "react-icons/fa6";
import {api} from "../api";

export default function Dashboard({profile,setProfile,vehicles,ownerId,setOwnerId,setPremium,onSaved,setTab}){
 const [lookupEmail,setLookupEmail]=useState("");
 const [lookupMessage,setLookupMessage]=useState("");
 const update=(k,v)=>setProfile(p=>({...p,[k]:v}));
 const v=vehicles[profile.vehicle];
 const save=async e=>{e.preventDefault();try{
   const x=await api("/api/profile",{method:"POST",body:JSON.stringify({owner_name:profile.ownerName,email:profile.ownerEmail,vehicle_id:profile.vehicle,registration:profile.registration,battery_pct:Number(profile.charge),personal_range_km:profile.personalRange?Number(profile.personalRange):null})});
   setOwnerId(x.id); onSaved(); setTab("planner");
 }catch(err){setLookupMessage(err.message)}};
 const load=async()=>{try{const x=await api(`/api/profile?email=${encodeURIComponent(lookupEmail)}`);setProfile({ownerName:x.owner_name,ownerEmail:x.email,vehicle:x.vehicle_id,registration:x.registration||"",charge:x.battery_pct,personalRange:x.personal_range_km??""});setOwnerId(x.id);setLookupMessage("Saved profile loaded from the backend database.")}catch(err){setLookupMessage(err.message)}};
 return <div className="page">
  <div className="hero rounded-4 p-4 p-lg-5 mb-4"><Row className="align-items-center g-4"><Col lg={7}><Badge bg="light" text="primary" className="mb-3">PERSONAL EV ROUTING</Badge><h1 className="display-5 fw-bold">Real roads. <span>Personalized EV planning.</span></h1><p className="lead text-secondary">Search places like a maps app, calculate the actual road route, inspect charger records and adapt range calculations to the owner's EV.</p><Button size="lg" onClick={()=>setTab("planner")} disabled={!ownerId}>Plan a journey →</Button></Col><Col lg={5}><div className="glass-card p-4"><div className="small text-secondary">CURRENT VEHICLE</div><h4>{v?.name||"Choose a vehicle"}</h4><div className="d-flex justify-content-between mt-3"><span>Battery</span><strong>{profile.charge}%</strong></div><div className="progress mt-2"><div className="progress-bar" style={{width:`${Math.max(0,Math.min(100,profile.charge))}%`}}/></div></div></Col></Row></div>
  <Row className="g-4"><Col lg={8}><Card className="shadow-sm border-0"><Card.Body className="p-4"><h3>Owner & Vehicle Profile</h3><p className="text-secondary">Nothing is pre-filled. Save the profile to the backend database or load an existing profile by email.</p>
   <Form onSubmit={save}><Row className="g-3"><Col md={6}><Form.Label>Owner name</Form.Label><Form.Control required value={profile.ownerName} onChange={e=>update("ownerName",e.target.value)} placeholder="Your name"/></Col>
   <Col md={6}><Form.Label>Email / account ID</Form.Label><Form.Control required type="email" value={profile.ownerEmail} onChange={e=>update("ownerEmail",e.target.value)} placeholder="you@example.com"/></Col>
   <Col md={6}><Form.Label>Vehicle model</Form.Label><Form.Select required value={profile.vehicle} onChange={e=>update("vehicle",e.target.value)}><option value="">Select your EV</option>{Object.entries(vehicles).map(([id,x])=><option key={id} value={id}>{x.name}</option>)}</Form.Select></Col>
   <Col md={6}><Form.Label>Registration (optional)</Form.Label><Form.Control value={profile.registration} onChange={e=>update("registration",e.target.value)} placeholder="Vehicle registration"/></Col>
   <Col md={6}><Form.Label>Current battery: {profile.charge}%</Form.Label><Form.Range min="0" max="100" value={profile.charge} onChange={e=>update("charge",Number(e.target.value))}/></Col>
   <Col md={6}><Form.Label>Your observed full-charge range (km)</Form.Label><Form.Control type="number" min="20" max="2000" value={profile.personalRange} onChange={e=>update("personalRange",e.target.value)} placeholder={v?`Optional; reference ${v.reference_range_km} km`:"Optional"}/><Form.Text>Used with the vehicle reference value to personalize energy estimates.</Form.Text></Col>
   <Col><Button type="submit" className="w-100">Save profile & continue</Button></Col></Row></Form>
  </Card.Body></Card></Col>
  <Col lg={4}><Card className="shadow-sm border-0 h-100"><Card.Body className="p-4"><h5><FaDatabase className="me-2"/>Load saved profile</h5><p className="small text-secondary">Use the same email you saved earlier. No owner data is hardcoded into the app.</p><InputGroup><Form.Control type="email" value={lookupEmail} onChange={e=>setLookupEmail(e.target.value)} placeholder="Saved email"/><Button variant="outline-primary" onClick={load} disabled={!lookupEmail}>Load</Button></InputGroup>{lookupMessage&&<Alert className="small mt-3" variant={lookupMessage.includes("loaded")?"success":"warning"}>{lookupMessage}</Alert>}
   <hr/><h5>Vehicle intelligence</h5><div className="mini-stat"><FaCar/><span>{v?.battery_kwh ?? "—"} kWh battery</span></div><div className="mini-stat"><FaGaugeHigh/><span>{v?.reference_range_km ?? "—"} km reference range</span></div><div className="mini-stat"><FaBolt/><span>{v?.dc_kw ?? "—"} kW max DC reference</span></div><div className="mini-stat"><FaRoute/><span>{v?.charging_port || "—"}</span></div><Alert variant="info" className="small mt-4 mb-0">Range model = vehicle reference data + owner observation, with a safety reserve.</Alert>
  </Card.Body></Card></Col></Row></div>
}
