import React,{useEffect,useState} from "react";
import {Container,Toast,ToastContainer,Spinner} from "react-bootstrap";
import Navbar from "./components/Navbar"; import Footer from "./components/Footer";
import Dashboard from "./components/Dashboard"; import Planner from "./components/Planner";
import Stations from "./components/Stations"; import Subscription from "./components/Subscription";
import DataConsole from "./components/DataConsole"; import {api} from "./api";

const emptyProfile={ownerName:"",ownerEmail:"",vehicle:"",registration:"",charge:0,personalRange:""};
export default function App(){
 const [tab,setTab]=useState("dashboard");
 const [dark,setDark]=useState(localStorage.getItem("ev_theme")==="dark");
 const [vehicles,setVehicles]=useState({});
 const [profile,setProfile]=useState(emptyProfile);
 const [premium,setPremium]=useState(false);
 const [ownerId,setOwnerId]=useState(null);
 const [toast,setToast]=useState("");
 const [loading,setLoading]=useState(true);
 useEffect(()=>{document.body.classList.toggle("dark",dark);localStorage.setItem("ev_theme",dark?"dark":"light")},[dark]);
 useEffect(()=>{api("/api/vehicles").then(setVehicles).catch(e=>setToast(e.message)).finally(()=>setLoading(false))},[]);
 if(loading)return <div className="loading-screen"><Spinner/><span>Loading EVChargeRoute…</span></div>;
 return <><Navbar tab={tab} setTab={setTab} dark={dark} setDark={setDark} premium={premium}/>
 <Container className="py-4">
  {tab==="dashboard"&&<Dashboard profile={profile} setProfile={setProfile} vehicles={vehicles} ownerId={ownerId} setOwnerId={setOwnerId} setPremium={setPremium} onSaved={()=>setToast("Profile saved in the backend database.")} setTab={setTab}/>} 
  {tab==="planner"&&<Planner profile={profile} vehicles={vehicles} premium={premium} ownerId={ownerId}/>} 
  {tab==="stations"&&<Stations/>}
  {tab==="subscription"&&<Subscription premium={premium} setPremium={setPremium} ownerId={ownerId} setOwnerId={setOwnerId} setToast={setToast}/>} 
  {tab==="data"&&<DataConsole/>}
 </Container><Footer/>
 <ToastContainer position="bottom-end" className="p-3"><Toast show={!!toast} onClose={()=>setToast("")} delay={3000} autohide><Toast.Body>{toast}</Toast.Body></Toast></ToastContainer></>
}
