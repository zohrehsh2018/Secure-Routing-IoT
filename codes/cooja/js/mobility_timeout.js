TIME_STEP_S = 1;
END_TIME_S  = 900;

TIMEOUT(END_TIME_S * 1000);

var File = java.io.File;
var FileReader = java.io.FileReader;
var BufferedReader = java.io.BufferedReader;

var projectDir = sim.getCooja().getProjectDir();
var mobilityPath = projectDir + "/examples/dataset-rpl/mobility.csv";
log.log("Using mobility file: " + mobilityPath + "\n");

var reader = new BufferedReader(new FileReader(new File(mobilityPath)));
var header = reader.readLine();

var mobility = {};
var line;
while((line = reader.readLine()) != null) {
  line = line.trim();
  if(line.length == 0) continue;

  var p = line.split(",");
  if(p.length < 4) continue;

  var t = parseInt(p[0]);
  var id = parseInt(p[1]);
  var x = parseFloat(p[2]);
  var y = parseFloat(p[3]);

  if(!mobility[t]) mobility[t] = {};
  mobility[t][id] = {x:x, y:y};
}
reader.close();

log.log("Loaded mobility for " + Object.keys(mobility).length + " time steps\n");

while(true) {
  YIELD();

  var now_s = Math.floor(time / 1000);

  if(mobility[now_s]) {
    var step = mobility[now_s];
    var motes = sim.getMotes();

    for(var idStr in step) {
      var id = parseInt(idStr);
      var pos = step[idStr];

      for(var i = 0; i < motes.length; i++) {
        if(motes[i].getID() == id) {
          var position = motes[i].getInterfaces().getPosition();
          position.setCoordinates(pos.x, pos.y, 0);
          break;
        }
      }
    }
  }

  GENERATE_ALARM(TIME_STEP_S * 1000);
}
