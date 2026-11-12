const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('token'), view = 'discover', selected = new Set(), playlists = [];
function message(text) { $('message').textContent = text; }
async function api(path, method='GET', body) {
  const response = await fetch('/api'+path, {method, headers:{'Content-Type':'application/json', ...(token?{Authorization:'Bearer '+token}:{})}, body:body===undefined?undefined:JSON.stringify(body)});
  const data = await response.json();
  if(!response.ok) throw Error(typeof data.detail === 'string'?data.detail:'Dữ liệu nhập không hợp lệ');
  return data;
}
function el(tag, text, cls) {const node=document.createElement(tag); if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
async function safe(fn) {try{await fn();}catch(error){message(error.message);}}
async function auth(register=false){
  const data=await api('/auth/'+(register?'register':'login'),'POST',{username:$('username').value,password:$('password').value});
  token=data.token;sessionStorage.setItem('token',token);$('password').value='';await boot();
}
$('authForm').onsubmit=e=>{e.preventDefault();safe(()=>auth());};
$('register').onclick=()=>safe(()=>auth(true));
$('logout').onclick=()=>{sessionStorage.removeItem('token');token=null;location.reload();};
async function feedback(track,type){await api('/events','POST',{event_id:crypto.randomUUID(),track_id:track.track_id,event_type:type});message('Đã ghi nhận phản hồi của bạn');if(view==='discover')await render();}
function card(track){
  const c=el('article',undefined,'card');c.append(el('div','♫','art'),el('h3',track.track_name),el('p',track.artists),el('small',track.genres));
  if(track.reason)c.append(el('small',track.reason));
  const actions=el('div',undefined,'actions');
  for(const [label,type] of [['♡ Thích','like'],['Ẩn','dislike'],['Bỏ thích','unlike']]){const b=el('button',label);b.onclick=()=>safe(()=>feedback(track,type));actions.append(b);}
  const link=el('a','Mở Spotify ↗');link.href='https://open.spotify.com/track/'+encodeURIComponent(track.track_id);link.target='_blank';link.rel='noopener noreferrer';link.onclick=()=>safe(()=>feedback(track,'open_spotify'));actions.append(link);
  if(playlists.length){const select=el('select');select.setAttribute('aria-label','Thêm vào playlist');const placeholder=el('option','+ Playlist');placeholder.value='';select.append(placeholder);for(const p of playlists){const option=el('option',p.name);option.value=p.id;select.append(option);}select.onchange=()=>safe(async()=>{if(select.value){await api(`/playlists/${select.value}/tracks/${encodeURIComponent(track.track_id)}`,'PUT');message('Đã thêm vào playlist');select.value='';}});actions.append(select);}
  c.append(actions);return c;
}
async function render(){
  $('preferences').hidden=view!=='discover';$('searchForm').hidden=view!=='search';$('playlistControls').hidden=view!=='playlists';$('content').replaceChildren();
  $('title').textContent={discover:'Dành cho bạn',search:'Khám phá',playlists:'Bộ sưu tập của bạn',analytics:'Hoạt động của bạn'}[view];
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
  playlists=await api('/playlists');
  if(view==='analytics'){
    const stats=await api('/analytics/me');$('subtitle').textContent=stats.note;
    for(const [key,value] of Object.entries(stats.counts)){const c=el('article',undefined,'card');c.append(el('span',key),el('div',value,'stat'));$('content').append(c);}
    for(const d of stats.daily){const c=el('article',undefined,'card');c.append(el('h3',d.date),el('p',d.events+' tương tác'));$('content').append(c);}return;
  }
  $('subtitle').textContent='Chọn một bài yêu thích để những gợi ý tiếp theo gần với bạn hơn.';
  if(view==='playlists'){for(const p of playlists){const c=el('section',undefined,'card');c.append(el('h3',p.name));for(const t of p.tracks)c.append(el('p',t.track_name+' — '+t.artists));$('content').append(c);}if(!playlists.length)$('content').append(el('p','Tạo playlist đầu tiên của bạn.'));return;}
  const tracks=await api(view==='discover'?'/recommendations':'/tracks?q='+encodeURIComponent($('query').value));
  tracks.forEach(t=>$('content').append(card(t)));if(!tracks.length)$('content').append(el('p','Chưa có kết quả phù hợp.'));
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(!token)return message('Đăng nhập để tiếp tục');view=b.dataset.view;safe(render);});
$('searchForm').onsubmit=e=>{e.preventDefault();safe(render);};
$('savePreferences').onclick=()=>safe(async()=>{await api('/me/preferences','PUT',{genres:[...selected]});message('Đã lưu sở thích');await render();});
$('newPlaylist').onclick=()=>safe(async()=>{await api('/playlists','POST',{name:$('playlistName').value});$('playlistName').value='';await render();});
async function boot(){
  const health=await api('/health');$('modelInfo').textContent=health.tracks.toLocaleString()+' bài hát · '+health.model;
  $('auth').hidden=!!token;$('workspace').hidden=!token;$('logout').hidden=!token;
  if(!token)return;
  let me;try{me=await api('/me');}catch(error){sessionStorage.removeItem('token');token=null;await boot();throw error;}
  selected=new Set(me.genres);$('genreList').replaceChildren();
  for(const genre of await api('/genres')){const b=el('button',genre,'chip');b.classList.toggle('selected',selected.has(genre));b.onclick=()=>{if(selected.has(genre))selected.delete(genre);else if(selected.size<20)selected.add(genre);else return message('Chọn tối đa 20 thể loại');b.classList.toggle('selected',selected.has(genre));};$('genreList').append(b);}
  await render();
}
safe(boot);
