import React from "react"; import {Navbar as BsNavbar,Nav,Container,Button,Badge} from "react-bootstrap"; import {FaBolt,FaMoon,FaSun} from "react-icons/fa";
export default function Navbar({tab,setTab,dark,setDark,premium}){
 const items=[["dashboard","Dashboard"],["planner","Route Planner"],["stations","Stations"],["subscription","Subscription"],["data","Data Console"]];
 return <BsNavbar expand="lg" sticky="top" className="app-nav border-bottom"><Container>
 <BsNavbar.Brand onClick={()=>setTab("dashboard")} className="brand" role="button"><span className="brand-icon"><FaBolt/></span> EVChargeRoute</BsNavbar.Brand>
 <BsNavbar.Toggle/><BsNavbar.Collapse><Nav className="me-auto">{items.map(([id,label])=><Nav.Link key={id} active={tab===id} onClick={()=>setTab(id)}>{label}</Nav.Link>)}</Nav>
 <div className="d-flex align-items-center gap-2"><Button variant="outline-secondary" size="sm" onClick={()=>setDark(!dark)}>{dark?<FaSun/>:<FaMoon/>} {dark?"Light":"Dark"}</Button><Badge bg={premium?"warning":"secondary"} text={premium?"dark":"light"}>{premium?"Premium":"Free"}</Badge></div>
 </BsNavbar.Collapse></Container></BsNavbar>
}
