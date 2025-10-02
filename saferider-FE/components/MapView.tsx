import { useEffect, useRef } from "react";

declare global {
  interface Window { kakao: any }
}

interface Person {
  id: string;
  name: string;
  status: "missing" | "found" | "searching";
  lat: number; // 위도
  lng: number; // 경도
}

interface MapViewProps {
  people: Person[];
  selectedPerson: Person | null;
  onPersonSelect: (person: Person) => void;
}

export function MapView({ people, selectedPerson, onPersonSelect }: MapViewProps) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapObj = useRef<any>(null);
  const inited = useRef(false);               // StrictMode 가드
  const markersRef = useRef<any[]>([]);
  const overlaysRef = useRef<any[]>([]);

  // 상태별 색상
  const colorByStatus = (s: Person["status"]) =>
    s === "missing" ? "#ef4444" : s === "found" ? "#16a34a" : "#eab308";

  // SVG 마커
  const markerImageFor = (status: Person["status"], selected: boolean) => {
    const color = colorByStatus(status);
    const stroke = selected ? "#3b82f6" : color;
    const svg = encodeURIComponent(
      `<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'>
        <g fill='none' fill-rule='evenodd'>
          <circle cx='16' cy='16' r='9' fill='white' stroke='${stroke}' stroke-width='3'/>
          <circle cx='16' cy='16' r='4' fill='${color}'/>
        </g>
      </svg>`
    );
    const imageSrc = `data:image/svg+xml;charset=UTF-8,${svg}`;
    return new window.kakao.maps.MarkerImage(
      imageSrc,
      new window.kakao.maps.Size(32, 32),
      { offset: new window.kakao.maps.Point(16, 16) }
    );
  };

  // 라벨 오버레이
  const overlayHTML = (p: Person) => {
    const bg = `${colorByStatus(p.status)}20`;
    const fg = colorByStatus(p.status);
    return `
      <div style="
        transform: translate(-50%, 8px);
        background: rgba(255,255,255,0.9);
        backdrop-filter: blur(6px);
        border:1px solid #e5e7eb;border-radius:8px;
        padding:4px 8px;font:12px/1.2 system-ui,-apple-system,Segoe UI,Roboto;
        white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,0.08);
      ">
        ${p.name}
        <span style="
          margin-left:6px;font-size:11px;padding:2px 6px;border-radius:6px;
          background:${bg};color:${fg};border:1px solid #e5e7eb;
        ">${p.status}</span>
      </div>
    `;
  };

  // Kakao SDK 보장 로더
  const ensureKakao = () =>
    new Promise<void>((resolve) => {
      if (window.kakao?.maps) return resolve();

      const id = "kakao-sdk";
      const exist = document.getElementById(id) as HTMLScriptElement | null;
      if (exist) {
        exist.addEventListener("load", () => window.kakao.maps.load(resolve), { once: true });
        return;
      }
      const s = document.createElement("script");
      s.id = id;
      const APPKEY = import.meta.env.VITE_KAKAO_JS_KEY;
      s.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${APPKEY}&autoload=false`;
      s.async = true;
      s.defer = true;
      s.onload = () => window.kakao.maps.load(resolve);
      document.head.appendChild(s);
    });

  // 1) 초기화(1회)
  useEffect(() => {
    if (inited.current) return;

    const init = async () => {
      await ensureKakao();
      if (!mapRef.current || inited.current) return;
      inited.current = true;

      const center = new window.kakao.maps.LatLng(
        selectedPerson?.lat ?? 36.5,
        selectedPerson?.lng ?? 127.8
      );
      mapObj.current = new window.kakao.maps.Map(mapRef.current, { center, level: 7 });
      mapObj.current.addControl(
        new window.kakao.maps.ZoomControl(),
        window.kakao.maps.ControlPosition.RIGHT
      );
      console.log("map init", mapRef.current?.clientWidth, mapRef.current?.clientHeight);
      window.kakao.maps.event.addListener(mapObj.current, "tilesloaded", () => console.log("tilesloaded"));
    };

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) 사람 목록/선택 변화 → 마커+오버레이 갱신
  useEffect(() => {
    if (!mapObj.current || !window.kakao?.maps) return;

    // 정리
    markersRef.current.forEach((m) => m.setMap(null));
    overlaysRef.current.forEach((o) => o.setMap(null));
    markersRef.current = [];
    overlaysRef.current = [];

    people.forEach((p) => {
      const pos = new window.kakao.maps.LatLng(p.lat, p.lng);
      const selected = selectedPerson?.id === p.id;

      const marker = new window.kakao.maps.Marker({
        position: pos,
        image: markerImageFor(p.status, selected),
        zIndex: selected ? 5 : 3,
      });
      marker.setMap(mapObj.current);
      window.kakao.maps.event.addListener(marker, "click", () => onPersonSelect(p));
      markersRef.current.push(marker);

      const overlay = new window.kakao.maps.CustomOverlay({
        position: pos,
        content: overlayHTML(p),
        yAnchor: 0,
        zIndex: selected ? 6 : 4,
      });
      overlay.setMap(mapObj.current);
      overlaysRef.current.push(overlay);
    });
    const bounds = new window.kakao.maps.LatLngBounds();
people.forEach(p => bounds.extend(new window.kakao.maps.LatLng(p.lat, p.lng)));
if (people.length) {
  mapObj.current.setBounds(bounds, 50, 50, 50, 50); // 좌상우하 패딩(px)
}
  }, [people, selectedPerson, onPersonSelect]);

  // 3) 선택 변경 시 센터 이동
  useEffect(() => {
    if (!mapObj.current) return;
    const ro = new ResizeObserver(() => {
      mapObj.current.relayout();
      if (selectedPerson) {
        const c = new window.kakao.maps.LatLng(selectedPerson.lat, selectedPerson.lng);
        mapObj.current.setCenter(c);
      }
    });
    if (mapRef.current) ro.observe(mapRef.current);
    // 최초 1회 강제
    setTimeout(() => mapObj.current && mapObj.current.relayout(), 0);
    return () => ro.disconnect();
  }, [selectedPerson]);

  return (
    <div className="relative h-full border rounded-lg overflow-hidden">
      <div ref={mapRef} className="w-full h-full min-h-[560px] bg-gray-50" />
    </div>
  );
}
