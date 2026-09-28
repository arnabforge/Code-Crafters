const BASE=import.meta.env.VITE_API_BASE||"http://localhost:8000";
export async function api(path,options={}){
 const response=await fetch(`${BASE}${path}`,{headers:{"Content-Type":"application/json",...(options.headers||{})},...options});
 const data=await response.json().catch(()=>({detail:"Invalid server response"}));
 if(!response.ok) throw new Error(data.detail||"Request failed");
 return data;
}
export {BASE};
