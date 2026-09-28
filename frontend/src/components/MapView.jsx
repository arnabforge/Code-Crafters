import React,{useEffect,useRef,useState} from "react";
import {Card,Alert} from "react-bootstrap";

const BROWSER_KEY=import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY || "";
let mapsPromise=null;
function loadGoogleMaps(){
 if(window.google?.maps) return Promise.resolve();
 if(!BROWSER_KEY) return Promise.reject(new Error("VITE_GOOGLE_MAPS_BROWSER_KEY is not configured."));
 if(mapsPromise) return mapsPromise;
 mapsPromise=new Promise((resolve,reject)=>{
  const existing=document.querySelector('script[data-ev-google-maps="true"]');
  if(existing){existing.addEventListener("load",resolve,{once:true});existing.addEventListener("error",()=>reject(new Error("Google Maps failed to load.")),{once:true});return;}
  const script=document.createElement("script");script.dataset.evGoogleMaps="true";script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(BROWSER_KEY)}&v=weekly`;script.async=true;script.defer=true;script.onload=resolve;script.onerror=()=>reject(new Error("Google Maps failed to load."));document.head.appendChild(script);
 });
 return mapsPromise;
}

export default function MapView({result}){
 const ref=useRef(null); const [msg,setMsg]=useState("");
 useEffect(()=>{let cancelled=false;async function go(){try{
  await loadGoogleMaps(); if(cancelled||!ref.current)return;
  const origin=result.origin,dest=result.destination;
  const map=new google.maps.Map(ref.current,{center:{lat:origin.lat,lng:origin.lng},zoom:8,mapTypeControl:false,streetViewControl:false,fullscreenControl:true});
  const bounds=new google.maps.LatLngBounds();
  new google.maps.Marker({map,position:origin,label:"A",title:result.origin.formatted});
  new google.maps.Marker({map,position:dest,label:"B",title:result.destination.formatted});
  bounds.extend(origin);bounds.extend(dest);
  (result.stations||[]).forEach(s=>{if(s.lat==null||s.lng==null)return;const m=new google.maps.Marker({map,position:{lat:Number(s.lat),lng:Number(s.lng)},title:`${s.name} — ${s.operator||""}`});const info=new google.maps.InfoWindow({content:`<div style="min-width:190px"><strong>${escapeHtml(s.name)}</strong><br>${escapeHtml(s.operator||"")}<br>Status: ${escapeHtml(s.status||"Not reported")}<br>Ports: ${escapeHtml((s.ports||[]).map(p=>p.type).join(", ")||"Not reported")}<br>Queue (simulation): ${s.queue ?? "—"}</div>`});m.addListener("click",()=>info.open({map,anchor:m}));bounds.extend({lat:Number(s.lat),lng:Number(s.lng)});});
  const path=decode(result.route.polyline); if(path.length){new google.maps.Polyline({map,path,strokeOpacity:.85,strokeWeight:5});path.forEach(p=>bounds.extend(p));}
  map.fitBounds(bounds);
 }catch(e){if(!cancelled)setMsg(e.message||"Map could not load. Check the browser key and API restrictions.")}}go();return()=>{cancelled=true}},[result]);
 return <Card className="shadow-sm border-0 mt-4"><Card.Body className="p-2">{msg&&<Alert className="m-2" variant="warning">{msg}</Alert>}<div ref={ref} className="map-box"></div></Card.Body></Card>
}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));}
function decode(str){const pts=[];let i=0,lat=0,lng=0;while(i<str.length){let r=0,s=0,b;do{b=str.charCodeAt(i++)-63;r|=(b&31)<<s;s+=5}while(b>=32);lat+=((r&1)?~(r>>1):(r>>1));r=0;s=0;do{b=str.charCodeAt(i++)-63;r|=(b&31)<<s;s+=5}while(b>=32);lng+=((r&1)?~(r>>1):(r>>1));pts.push({lat:lat/1e5,lng:lng/1e5})}return pts}
