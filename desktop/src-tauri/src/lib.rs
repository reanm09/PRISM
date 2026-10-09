use notify::{Config, Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use reqwest::multipart::{Form, Part};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    sync::Mutex,
    time::{Duration, SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, State};

#[derive(Clone, Serialize, Deserialize, Debug)]
pub struct ScanResult {
    pub path: String,
    pub name: String,
    pub extension: String,
    pub size_bytes: u64,
    pub sha256: String,
    pub declared_type: String,
    pub detected_type: String,
    pub entropy: f64,
    pub markers: Vec<String>,
    pub status: String,
    pub reason: Option<String>,
    pub risk_score: u8,
    pub risk_factors: Vec<String>,
    pub scanned_at: String,
}

#[derive(Clone, Serialize, Deserialize)]
pub struct HistoryItem {
    pub id: String,
    #[serde(flatten)]
    pub result: ScanResult,
}

#[derive(Clone, Serialize, Deserialize)]
pub struct QuarantineItem {
    pub id: String,
    pub name: String,
    pub original_path: String,
    pub quarantined_path: String,
    pub sha256: String,
    pub risk_score: u8,
    pub risk_factors: Vec<String>,
    pub declared_type: String,
    pub detected_type: String,
    pub size_bytes: u64,
    pub quarantined_at: String,
    pub scan_status: String,
}

#[derive(Clone, Serialize, Deserialize, Default)]
pub struct Settings {
    pub api_url: String,
    pub quarantine_dir: String,
    pub max_file_mb: u64,
}

#[derive(Clone, Serialize)]
pub struct BatchScanResult {
    pub directory: String,
    pub scanned: usize,
    pub review: usize,
    pub clear: usize,
    pub failed: usize,
}

pub struct AppState {
    watches: Mutex<Vec<String>>,
    watchers: Mutex<HashMap<String, RecommendedWatcher>>,
    history: Mutex<Vec<HistoryItem>>,
    quarantined: Mutex<Vec<QuarantineItem>>,
    settings: Mutex<Settings>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            watches: Mutex::new(Vec::new()),
            watchers: Mutex::new(HashMap::new()),
            history: Mutex::new(Vec::new()),
            quarantined: Mutex::new(Vec::new()),
            settings: Mutex::new(Settings {
                api_url: "http://127.0.0.1:8000".into(),
                quarantine_dir: String::new(),
                max_file_mb: 100,
            }),
        }
    }
}

fn now_isoish() -> String {
    let secs = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs();
    format!("unix:{secs}")
}

fn app_dirs(app: &AppHandle) -> Result<(PathBuf, PathBuf), String> {
    let data = app.path().app_data_dir().map_err(|e| e.to_string())?;
    let q = data.join("Quarantine");
    fs::create_dir_all(&data).map_err(|e| e.to_string())?;
    fs::create_dir_all(&q).map_err(|e| e.to_string())?;
    Ok((data, q))
}

fn declared_type(path: &Path) -> String {
    match path.extension().and_then(|x| x.to_str()).unwrap_or("").to_lowercase().as_str() {
        "pdf" => "application/pdf",
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "zip" => "application/zip",
        "docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "exe" => "application/vnd.microsoft.portable-executable",
        "dll" => "application/x-dll",
        "txt" => "text/plain",
        _ => "application/octet-stream",
    }.to_string()
}

fn magic_type(bytes: &[u8]) -> String {
    if bytes.starts_with(b"%PDF-") { "application/pdf" }
    else if bytes.starts_with(b"\x89PNG\r\n\x1a\n") { "image/png" }
    else if bytes.starts_with(&[0xFF, 0xD8, 0xFF]) { "image/jpeg" }
    else if bytes.starts_with(b"GIF8") { "image/gif" }
    else if bytes.starts_with(b"PK\x03\x04") { "application/zip" }
    else if bytes.starts_with(b"MZ") { "application/vnd.microsoft.portable-executable" }
    else if bytes.starts_with(b"RIFF") { "application/octet-stream (RIFF)" }
    else { "unknown" }
    .to_string()
}

fn entropy(bytes: &[u8]) -> f64 {
    if bytes.is_empty() { return 0.0; }
    let mut counts = [0u64; 256];
    for b in bytes { counts[*b as usize] += 1; }
    let len = bytes.len() as f64;
    counts.iter().filter(|&&c| c > 0).map(|&c| {
        let p = c as f64 / len;
        -p * p.log2()
    }).sum()
}

fn contains_ascii(bytes: &[u8], needle: &[u8]) -> bool {
    !needle.is_empty() && bytes.windows(needle.len()).any(|w| w == needle)
}

fn analyze_markers(bytes: &[u8], detected: &str) -> Vec<String> {
    let mut out = Vec::new();
    if detected == "application/pdf" {
        let markers = [
            (b"/JavaScript".as_slice(), "PDF JavaScript marker"),
            (b"/JS".as_slice(), "PDF /JS action marker"),
            (b"/OpenAction".as_slice(), "PDF OpenAction marker"),
            (b"/AA".as_slice(), "PDF additional-action marker"),
            (b"/Launch".as_slice(), "PDF Launch action marker"),
            (b"/RichMedia".as_slice(), "PDF RichMedia marker"),
            (b"/EmbeddedFile".as_slice(), "PDF embedded-file marker"),
            (b"/AcroForm".as_slice(), "PDF AcroForm marker"),
            (b"/XFA".as_slice(), "PDF XFA marker"),
        ];
        for (needle, label) in markers {
            if contains_ascii(bytes, needle) { out.push(label.to_string()); }
        }
    }
    if detected == "application/vnd.microsoft.portable-executable" {
        out.push("PE executable signature observed".into());
    }
    if bytes.len() > 5 * 1024 * 1024 && entropy(bytes) > 7.4 {
        out.push("High byte entropy".into());
    }
    out
}

fn risk_profile(declared: &str, detected: &str, markers: &[String], ent: f64) -> (u8, Vec<String>) {
    let mut score: u16 = 0;
    let mut factors = Vec::new();
    if declared != "application/octet-stream" && detected != "unknown" && declared != detected {
        score += 45;
        factors.push(format!("Claimed type {} differs from observed {}", declared, detected));
    }
    for marker in markers {
        let add = if marker.contains("PE executable") { 40 } else if marker.contains("JavaScript") || marker.contains("/JS") || marker.contains("OpenAction") || marker.contains("Launch") { 20 } else if marker.contains("EmbeddedFile") || marker.contains("RichMedia") || marker.contains("XFA") { 14 } else { 10 };
        score += add;
        factors.push(marker.clone());
    }
    if ent >= 7.4 {
        score += 15;
        factors.push(format!("High byte entropy ({ent:.2}/8.00)"));
    }
    if detected == "unknown" && declared != "application/octet-stream" {
        score += 20;
        factors.push("Declared format has no recognized magic signature".into());
    }
    let score = score.min(100) as u8;
    if factors.is_empty() {
        factors.push("No elevated local evidence observed".into());
    }
    (score, factors)
}

fn status_for(score: u8, declared: &str, detected: &str, markers: &[String]) -> (String, Option<String>) {
    let mismatch = declared != "application/octet-stream" && detected != "unknown" && declared != detected;
    let has_active = markers.iter().any(|m| m.contains("JavaScript") || m.contains("/JS") || m.contains("OpenAction") || m.contains("Launch") || m.contains("PE executable"));
    if mismatch || !markers.is_empty() || score >= 50 {
        let reason = if mismatch {
            "Declared and observed identities disagree".into()
        } else if has_active {
            "FastScan observed active-content or executable evidence".into()
        } else {
            "FastScan observed elevated local evidence".into()
        };
        ("REVIEW".into(), Some(reason))
    } else {
        ("CLEAR".into(), None)
    }
}

fn insert_history(app: &AppHandle, state: &AppState, result: ScanResult) -> Result<(), String> {
    let mut hist = state.history.lock().map_err(|_| "state lock failed")?;
    hist.retain(|x| x.result.sha256 != result.sha256);
    hist.insert(0, HistoryItem { id: result.sha256.chars().take(12).collect(), result: result.clone() });
    if hist.len() > 500 { hist.truncate(500); }
    drop(hist);
    persist_history(app, state)?;
    let _ = app.emit("sentinel://scan-complete", result);
    Ok(())
}

fn scan_path_internal(app: &AppHandle, state: &AppState, path: &str) -> Result<ScanResult, String> {
    let p = PathBuf::from(path);
    if !p.is_file() { return Err("The selected path is not a file.".into()); }
    let metadata = fs::metadata(&p).map_err(|e| e.to_string())?;
    let settings = state.settings.lock().map_err(|_| "state lock failed")?.clone();
    if metadata.len() > settings.max_file_mb.saturating_mul(1024 * 1024) {
        return Err(format!("File exceeds Sentinel limit of {} MB", settings.max_file_mb));
    }
    let bytes = fs::read(&p).map_err(|e| e.to_string())?;
    let mut sha = Sha256::new();
    sha.update(&bytes);
    let hash = hex::encode(sha.finalize());
    let detected = magic_type(&bytes);
    let declared = declared_type(&p);
    let ent = entropy(&bytes);
    let markers = analyze_markers(&bytes, &detected);
    let (risk_score, risk_factors) = risk_profile(&declared, &detected, &markers, ent);
    let (status, reason) = status_for(risk_score, &declared, &detected, &markers);
    let result = ScanResult {
        path: path.into(),
        name: p.file_name().and_then(|s| s.to_str()).unwrap_or("artifact").into(),
        extension: p.extension().and_then(|s| s.to_str()).unwrap_or("").into(),
        size_bytes: metadata.len(),
        sha256: hash,
        declared_type: declared,
        detected_type: detected,
        entropy: ent,
        markers,
        status,
        reason,
        risk_score,
        risk_factors,
        scanned_at: now_isoish(),
    };
    insert_history(app, state, result.clone())?;
    Ok(result)
}

fn persist_history(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let (data, _) = app_dirs(app)?;
    let history = state.history.lock().map_err(|_| "state lock failed")?;
    let payload = serde_json::to_vec_pretty(&*history).map_err(|e| e.to_string())?;
    fs::write(data.join("history.json"), payload).map_err(|e| e.to_string())
}

fn load_history(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let (data, _) = app_dirs(app)?;
    let file = data.join("history.json");
    if !file.exists() { return Ok(()); }
    let bytes = fs::read(file).map_err(|e| e.to_string())?;
    let items: Vec<HistoryItem> = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    *state.history.lock().map_err(|_| "state lock failed")? = items;
    Ok(())
}

fn persist_quarantine(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let (data, _) = app_dirs(app)?;
    let items = state.quarantined.lock().map_err(|_| "state lock failed")?;
    let payload = serde_json::to_vec_pretty(&*items).map_err(|e| e.to_string())?;
    fs::write(data.join("quarantine.json"), payload).map_err(|e| e.to_string())
}

fn load_quarantine(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let (data, _) = app_dirs(app)?;
    let file = data.join("quarantine.json");
    if !file.exists() { return Ok(()); }
    let bytes = fs::read(file).map_err(|e| e.to_string())?;
    let items: Vec<QuarantineItem> = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    *state.quarantined.lock().map_err(|_| "state lock failed")? = items;
    Ok(())
}

fn persist_watches(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let (data, _) = app_dirs(app)?;
    let watches = state.watches.lock().map_err(|_| "state lock failed")?;
    let payload = serde_json::to_vec_pretty(&*watches).map_err(|e| e.to_string())?;
    fs::write(data.join("watches.json"), payload).map_err(|e| e.to_string())
}

fn load_watches(app: &AppHandle, state: &AppState) -> Result<Vec<String>, String> {
    let (data, _) = app_dirs(app)?;
    let file = data.join("watches.json");
    if !file.exists() { return Ok(Vec::new()); }
    let bytes = fs::read(file).map_err(|e| e.to_string())?;
    let items: Vec<String> = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    *state.watches.lock().map_err(|_| "state lock failed")? = items.clone();
    Ok(items)
}

#[tauri::command]
fn pick_file() -> Option<String> {
    rfd::FileDialog::new().set_title("Select artifact to scan").pick_file().map(|p| p.to_string_lossy().to_string())
}

#[tauri::command]
fn pick_folder() -> Option<String> {
    rfd::FileDialog::new().set_title("Select local folder").pick_folder().map(|p| p.to_string_lossy().to_string())
}

#[tauri::command]
fn scan_file(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<ScanResult, String> {
    scan_path_internal(&app, state.inner(), &path)
}

#[tauri::command]
fn scan_directory(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<BatchScanResult, String> {
    let root = PathBuf::from(&path);
    if !root.is_dir() { return Err("The selected path is not a folder.".into()); }
    let mut scanned = 0usize;
    let mut review = 0usize;
    let mut clear = 0usize;
    let mut failed = 0usize;
    let mut stack = vec![root.clone()];
    while let Some(dir) = stack.pop() {
        let entries = match fs::read_dir(&dir) { Ok(e) => e, Err(_) => { failed += 1; continue; } };
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_dir() { stack.push(p); continue; }
            if !p.is_file() { continue; }
            match scan_path_internal(&app, state.inner(), &p.to_string_lossy()) {
                Ok(result) => {
                    scanned += 1;
                    if result.status == "REVIEW" { review += 1; } else { clear += 1; }
                    if scanned >= 500 { return Ok(BatchScanResult { directory: path, scanned, review, clear, failed }); }
                }
                Err(_) => failed += 1,
            }
        }
    }
    Ok(BatchScanResult { directory: path, scanned, review, clear, failed })
}

#[tauri::command]
fn get_history(state: State<'_, AppState>) -> Result<Vec<HistoryItem>, String> {
    Ok(state.history.lock().map_err(|_| "state lock failed")?.clone())
}

#[tauri::command]
fn clear_history(app: AppHandle, state: State<'_, AppState>) -> Result<(), String> {
    state.history.lock().map_err(|_| "state lock failed")?.clear();
    persist_history(&app, state.inner())
}

#[tauri::command]
fn get_watches(state: State<'_, AppState>) -> Result<Vec<String>, String> {
    Ok(state.watches.lock().map_err(|_| "state lock failed")?.clone())
}

fn watch_one(app: &AppHandle, state: &AppState, path: &str) -> Result<(), String> {
    let app_handle = app.clone();
    let watch_key = path.to_string();
    let callback = move |res: notify::Result<Event>| {
        if let Ok(event) = res {
            if !matches!(event.kind, EventKind::Create(_) | EventKind::Modify(_)) { return; }
            for p in event.paths {
                if !p.is_file() { continue; }
                let path_string = p.to_string_lossy().to_string();
                let app_for_scan = app_handle.clone();
                std::thread::spawn(move || {
                    std::thread::sleep(std::time::Duration::from_millis(800));
                    let state = app_for_scan.state::<AppState>();
                    match scan_path_internal(&app_for_scan, state.inner(), &path_string) {
                        Ok(result) if result.status == "REVIEW" => {
                            let _ = app_for_scan.emit("sentinel://artifact-detected", serde_json::json!({
                                "path": result.path,
                                "name": result.name,
                                "reason": result.reason.unwrap_or_else(|| "Artifact routed to review".into()),
                                "risk_score": result.risk_score
                            }));
                        }
                        _ => {}
                    }
                });
            }
        }
    };
    let mut watcher = RecommendedWatcher::new(callback, Config::default()).map_err(|e| e.to_string())?;
    watcher.watch(Path::new(path), RecursiveMode::Recursive).map_err(|e| e.to_string())?;
    state.watchers.lock().map_err(|_| "state lock failed")?.insert(watch_key, watcher);
    Ok(())
}

#[tauri::command]
fn add_watch(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<(), String> {
    if !Path::new(&path).is_dir() { return Err("Watch location must be a folder.".into()); }
    {
        let mut list = state.watches.lock().map_err(|_| "state lock failed")?;
        if list.iter().any(|p| p == &path) { return Ok(()); }
        list.push(path.clone());
    }
    watch_one(&app, state.inner(), &path)?;
    persist_watches(&app, state.inner())
}

#[tauri::command]
fn remove_watch(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<(), String> {
    state.watches.lock().map_err(|_| "state lock failed")?.retain(|p| p != &path);
    state.watchers.lock().map_err(|_| "state lock failed")?.remove(&path);
    persist_watches(&app, state.inner())
}

#[tauri::command]
fn scan_watched_folder(app: AppHandle, state: State<'_, AppState>, path: String) -> Result<BatchScanResult, String> {
    scan_directory(app, state, path)
}

#[tauri::command]
fn get_quarantine(state: State<'_, AppState>) -> Result<Vec<QuarantineItem>, String> {
    Ok(state.quarantined.lock().map_err(|_| "state lock failed")?.clone())
}

#[tauri::command]
fn restore_quarantine(app: AppHandle, state: State<'_, AppState>, id: String) -> Result<String, String> {
    let item = {
        let list = state.quarantined.lock().map_err(|_| "state lock failed")?;
        list.iter().find(|x| x.id == id).cloned().ok_or("Quarantined artifact not found")?
    };
    let src = PathBuf::from(&item.quarantined_path);
    if !src.is_file() { return Err("Quarantined payload is missing.".into()); }
    let original = PathBuf::from(&item.original_path);
    let parent = original.parent().ok_or("Original folder could not be determined")?;
    if !parent.is_dir() { return Err("Original folder no longer exists; restore manually from the quarantine folder.".into()); }
    let mut dest = original.clone();
    if dest.exists() {
        let base = original.file_name().and_then(|n| n.to_str()).unwrap_or("restored_artifact");
        let mut candidate = parent.join(format!("{base}.restored"));
        let mut i = 2;
        while candidate.exists() {
            candidate = parent.join(format!("{base}.restored{i}"));
            i += 1;
        }
        dest = candidate;
    }
    fs::rename(&src, &dest)
        .or_else(|_| { fs::copy(&src, &dest).map(|_| ()).and_then(|_| fs::remove_file(&src)) })
        .map_err(|e| e.to_string())?;
    let restored_path = dest.to_string_lossy().to_string();
    {
        let mut list = state.quarantined.lock().map_err(|_| "state lock failed")?;
        list.retain(|x| x.id != id);
    }
    {
        let mut hist = state.history.lock().map_err(|_| "state lock failed")?;
        for h in hist.iter_mut() {
            if h.result.sha256 == id {
                h.result.path = restored_path.clone();
                h.result.status = item.scan_status.clone();
            }
        }
    }
    persist_history(&app, state.inner())?;
    persist_quarantine(&app, state.inner())?;
    let _ = app.emit("sentinel://quarantine-changed", serde_json::json!({"id": id, "restored": restored_path.clone()}));
    Ok(restored_path)
}

#[tauri::command]
fn reveal_file(path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    std::process::Command::new("explorer.exe").args(["/select,", &path]).spawn().map_err(|e| e.to_string())?;
    #[cfg(not(target_os = "windows"))]
    let _ = path;
    Ok(())
}

#[tauri::command]
fn open_quarantine_folder(app: AppHandle) -> Result<String, String> {
    let (_, q) = app_dirs(&app)?;
    #[cfg(target_os = "windows")]
    std::process::Command::new("explorer.exe").arg(q.to_string_lossy().to_string()).spawn().map_err(|e| e.to_string())?;
    Ok(q.to_string_lossy().to_string())
}

fn local_api_base(api_url: &str) -> Result<String, String> {
    let url = reqwest::Url::parse(api_url.trim()).map_err(|e| e.to_string())?;
    if url.scheme() != "http" || !matches!(url.host_str(), Some("127.0.0.1" | "localhost" | "::1"))
        || url.username() != "" || url.password().is_some() || url.path() != "/"
        || url.query().is_some() || url.fragment().is_some() {
        return Err("PRISM backend endpoint must be a loopback HTTP origin".into());
    }
    Ok(url.as_str().trim_end_matches('/').to_string())
}

#[tauri::command]
async fn backend_request(
    api_url: String,
    path: String,
    method: String,
    body: Option<String>,
) -> Result<serde_json::Value, String> {
    let method = method.parse::<reqwest::Method>().map_err(|e| e.to_string())?;
    if !(path == "/health" || path.starts_with("/api/")) || path.starts_with("//") {
        return Err("Unsupported backend path".into());
    }
    let client = reqwest::Client::builder().timeout(Duration::from_secs(120)).build().map_err(|e| e.to_string())?;
    let url = format!("{}{}", local_api_base(&api_url)?, path);
    let mut request = client.request(method, url);
    if let Some(raw) = body {
        let value: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
        request = request.json(&value);
    }
    let response = request.send().await.map_err(|e| e.to_string())?;
    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    let value: serde_json::Value = if text.trim().is_empty() {
        serde_json::Value::Null
    } else {
        serde_json::from_str(&text).unwrap_or_else(|_| serde_json::json!({"raw": text}))
    };
    if !status.is_success() {
        let detail = value.get("detail").and_then(|v| v.as_str()).unwrap_or("Backend request failed");
        return Err(format!("HTTP {}: {}", status.as_u16(), detail));
    }
    Ok(value)
}

#[tauri::command]
async fn handoff_artifact(path: String, api_url: String) -> Result<serde_json::Value, String> {
    let bytes = fs::read(&path).map_err(|e| e.to_string())?;
    let sha256 = format!("{:x}", Sha256::digest(&bytes));
    let name = Path::new(&path).file_name().and_then(|x| x.to_str()).unwrap_or("artifact").to_string();
    let part = Part::bytes(bytes).file_name(name);
    let form = Form::new().part("file", part);
    let client = reqwest::Client::builder().timeout(Duration::from_secs(120)).build().map_err(|e| e.to_string())?;
    let url = format!("{}/api/artifacts", local_api_base(&api_url)?);
    let response = client.post(url).multipart(form).send().await.map_err(|e| e.to_string())?;
    if !response.status().is_success() { return Err(format!("Artifact upload failed: HTTP {}", response.status().as_u16())); }
    let value: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    let id = value.get("artifact_id").and_then(|v| v.as_str()).ok_or("Artifact upload returned no artifact ID")?;
    if value.get("sha256").and_then(|v| v.as_str()) != Some(sha256.as_str()) {
        return Err("Uploaded artifact SHA-256 does not match local bytes".into());
    }
    Ok(serde_json::json!({"artifact_id": id, "message": "Artifact uploaded to PRISM."}))
}

#[tauri::command]
fn get_settings(app: AppHandle, state: State<'_, AppState>) -> Result<Settings, String> {
    let mut settings = state.settings.lock().map_err(|_| "state lock failed")?;
    if settings.api_url.is_empty() { settings.api_url = "http://127.0.0.1:8000".into(); }
    let (_, q) = app_dirs(&app)?;
    settings.quarantine_dir = q.to_string_lossy().to_string();
    Ok(settings.clone())
}

#[tauri::command]
fn set_api_url(state: State<'_, AppState>, api_url: String) -> Result<(), String> {
    state.settings.lock().map_err(|_| "state lock failed")?.api_url = local_api_base(&api_url)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            let state = app.state::<AppState>();
            let _ = get_settings(app.handle().clone(), state.clone());
            let _ = load_history(&app.handle(), state.inner());
            let _ = load_quarantine(&app.handle(), state.inner());
            if let Ok(paths) = load_watches(&app.handle(), state.inner()) {
                for path in paths { let _ = watch_one(&app.handle(), state.inner(), &path); }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            pick_file,
            pick_folder,
            scan_file,
            scan_directory,
            scan_watched_folder,
            get_history,
            clear_history,
            get_watches,
            add_watch,
            remove_watch,
            get_quarantine,
            restore_quarantine,
            reveal_file,
            open_quarantine_folder,
            get_settings,
            set_api_url,
            backend_request,
            handoff_artifact,
        ])
        .run(tauri::generate_context!())
        .expect("error while running PRISM Sentinel");
}
