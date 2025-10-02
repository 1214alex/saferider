import { Camera, Search, AlertTriangle, MapPin, Clock, Eye, EyeOff, Play, Pause } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { useState } from "react";

interface CCTVCamera {
  id: string;
  name: string;
  location: string;
  status: "online" | "offline" | "recording";
  lat: number;
  lng: number;
  lastDetection?: string;
  detectionType?: "person" | "vehicle" | "motion";
  isActive: boolean;
}

interface CCTVPageProps {
  cameras: CCTVCamera[];
}

export function CCTVPage({ cameras }: CCTVPageProps) {
  const [selectedCamera, setSelectedCamera] = useState<CCTVCamera | null>(cameras[0] || null);
  const [searchQuery, setSearchQuery] = useState("");
  
  const onlineCameras = cameras.filter(c => c.status === 'online').length;
  const recordingCameras = cameras.filter(c => c.status === 'recording').length;
  const recentDetections = cameras.filter(c => c.lastDetection).length;

  const filteredCameras = cameras.filter(camera =>
    camera.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    camera.location.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="h-full flex gap-4">
      {/* Left Panel - Camera List */}
      <div className="w-80 flex flex-col">
        <Card className="h-full">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2">
              <Camera className="w-5 h-5 text-blue-600" />
              CCTV Network
            </CardTitle>
            <div className="flex gap-4 text-sm text-muted-foreground">
              <span>{onlineCameras} online</span>
              <span>{recordingCameras} recording</span>
              <span>{recentDetections} alerts</span>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2 top-2.5 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search cameras..."
                className="w-full pl-8 pr-3 py-2 border rounded-md text-sm"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Camera List */}
            <div className="space-y-2 max-h-[calc(100vh-300px)] overflow-auto">
              {filteredCameras.map((camera) => (
                <div
                  key={camera.id}
                  className={`p-3 border rounded-lg cursor-pointer transition-all duration-200 hover:shadow-md ${
                    selectedCamera?.id === camera.id ? 'ring-2 ring-blue-500 bg-blue-50' : ''
                  }`}
                  onClick={() => setSelectedCamera(camera)}
                >
                  <div className="flex items-start gap-3">
                    <div className={`p-1.5 rounded-lg ${
                      camera.status === 'online' 
                        ? 'bg-green-100' 
                        : camera.status === 'recording'
                        ? 'bg-blue-100'
                        : 'bg-gray-100'
                    }`}>
                      <Camera className={`w-3 h-3 ${
                        camera.status === 'online' 
                          ? 'text-green-600' 
                          : camera.status === 'recording'
                          ? 'text-blue-600'
                          : 'text-gray-600'
                      }`} />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="truncate text-sm">{camera.name}</h4>
                        <Badge 
                          variant="outline"
                          className={`text-xs ${
                            camera.status === 'online' 
                              ? 'border-green-500 text-green-700 bg-green-50' 
                              : camera.status === 'recording'
                              ? 'border-blue-500 text-blue-700 bg-blue-50'
                              : 'border-gray-500 text-gray-700 bg-gray-50'
                          }`}
                        >
                          {camera.status}
                        </Badge>
                      </div>
                      
                      <div className="text-xs text-muted-foreground mb-1">
                        <div className="flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          <span>{camera.location}</span>
                        </div>
                      </div>

                      {camera.lastDetection && (
                        <div className="flex items-center gap-1">
                          <div className={`w-2 h-2 rounded-full ${
                            camera.detectionType === 'person' ? 'bg-red-500' :
                            camera.detectionType === 'vehicle' ? 'bg-yellow-500' : 'bg-blue-500'
                          }`} />
                          <span className="text-xs text-muted-foreground">
                            {camera.detectionType} - {camera.lastDetection}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Right Panel - Camera Feed and Controls */}
      <div className="flex-1 flex flex-col gap-4">
        {selectedCamera ? (
          <>
            {/* Main Camera Feed */}
            <Card className="flex-1">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <Camera className="w-4 h-4" />
                    {selectedCamera.name}
                  </CardTitle>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline">
                      <Eye className="w-3 h-3 mr-1" />
                      {selectedCamera.isActive ? 'Hide' : 'Show'}
                    </Button>
                    <Button size="sm" variant="outline">
                      {selectedCamera.status === 'recording' ? (
                        <>
                          <Pause className="w-3 h-3 mr-1" />
                          Stop
                        </>
                      ) : (
                        <>
                          <Play className="w-3 h-3 mr-1" />
                          Record
                        </>
                      )}
                    </Button>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{selectedCamera.location}</p>
              </CardHeader>
              
              <CardContent>
                {/* Mock Live Feed */}
                <div className="aspect-video bg-gray-900 rounded-lg relative overflow-hidden mb-4">
                  <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900" />
                  <div className="absolute top-4 left-4 bg-red-600 text-white text-xs px-3 py-1 rounded flex items-center gap-2">
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    LIVE
                  </div>
                  <div className="absolute bottom-4 left-4 text-white text-sm">
                    {selectedCamera.location}
                  </div>
                  <div className="absolute bottom-4 right-4 text-white text-xs">
                    {new Date().toLocaleTimeString()}
                  </div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-white/60">Live Camera Feed</div>
                  </div>
                  
                  {/* Mock detection overlay */}
                  {selectedCamera.lastDetection && (
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                      <div className="border-2 border-red-500 bg-red-500/20 rounded-lg p-2">
                        <div className="text-white text-xs">
                          {selectedCamera.detectionType?.toUpperCase()} DETECTED
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <Button className="flex-1">
                    <Search className="w-3 h-3 mr-1" />
                    AI Person Search
                  </Button>
                  <Button variant="outline" className="flex-1">
                    <Clock className="w-3 h-3 mr-1" />
                    Playback
                  </Button>
                  <Button variant="outline" className="flex-1">
                    <AlertTriangle className="w-3 h-3 mr-1" />
                    Set Alert
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Detection Alerts */}
            {selectedCamera.lastDetection && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Recent Detections</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="p-3 bg-yellow-50 rounded-lg border">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-600" />
                      <span className="text-sm">{selectedCamera.detectionType?.toUpperCase()} DETECTION</span>
                      <Badge variant="outline" className="text-xs">
                        {selectedCamera.lastDetection}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Detected at {selectedCamera.location} - Confidence: 94%
                    </p>
                    <div className="flex gap-2 mt-2">
                      <Button size="sm" variant="outline" className="text-xs">
                        Review Footage
                      </Button>
                      <Button size="sm" variant="outline" className="text-xs">
                        False Positive
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <Card className="flex-1">
            <CardContent className="flex items-center justify-center h-full">
              <div className="text-center text-muted-foreground">
                <Camera className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Select a camera to view the feed</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}