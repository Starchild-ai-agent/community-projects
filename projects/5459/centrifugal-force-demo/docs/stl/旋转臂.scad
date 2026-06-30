arm_length=380;arm_width=24;arm_height=10;center_hole_r=8;
slot_x=155;slot_len=30;slot_w=18;
difference(){
  cube([arm_length,arm_width,arm_height],center=true);
  cylinder(h=arm_height+2,r=center_hole_r,center=true,$fn=48);
  translate([slot_x+slot_len/2-arm_length/2+190,0,0])
    cube([slot_len,slot_w,arm_height+2],center=true);
}
