outer_x=40;outer_y=30;outer_z=24;wall=3;base=3;
difference(){
  cube([outer_x,outer_y,outer_z],center=true);
  translate([0,0,base/2])cube([outer_x-2*wall,outer_y-2*wall,outer_z-base+1],center=true);
  cylinder(h=outer_z+2,r=1.5,center=true,$fn=24);
}
