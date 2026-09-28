import React from "react";
import {Container} from "react-bootstrap";
const teamName=import.meta.env.VITE_TEAM_NAME || "EVChargeRoute";
const teamMembers=import.meta.env.VITE_TEAM_MEMBERS || "";
export default function Footer(){return <footer className="footer mt-5 py-4 border-top"><Container className="d-flex flex-wrap justify-content-between gap-3"><div><strong>{teamName}</strong><div className="text-secondary small">Real-route + charger-data academic prototype</div></div>{teamMembers&&<div className="text-secondary small">{teamMembers}</div>}</Container></footer>}
