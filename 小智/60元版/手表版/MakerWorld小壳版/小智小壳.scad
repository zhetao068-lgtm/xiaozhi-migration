// Derived from Generic Electronics Enclosure, © 2025 Danish Raza (yeomann).
// Original: https://makerworld.com/en/models/2181679-generic-electronics-enclosure
// Original GitHub snapshot and CC BY-NC 4.0 license are in 01-原模型/.
// Modified: parameter sizing, rounded outline, selective openings, fasteners,
// PCB shelf/tray, and integral strap eyes. This adaptation is CC BY-NC 4.0.
// OpenSCAD -D 'part="..."': shell, bezel, trial, tray, gauge, assembled.
part = "shell";
$fn = 32;
eps = 0.04;

// Upstream parametric enclosure: shell = outer cube - inner cavity - edge slots;
// lid = perimeter lip + top plate. Dimensions and individual cuts adapted below.
inner_x = 44.8;
inner_y = 48.8;
inner_z = 19.2;
wall = 2.4;
base_thickness = 2.4;
outer_x = inner_x + wall * 2;
outer_y = inner_y + wall * 2;
outer_z = inner_z + base_thickness;
lid_plate = 2.4;
lid_lip = 1.0;
tolerance = 0.40;
slot_width = 22.0;
slot_height = 9.4;

board_x = 40.0;
board_y = 40.0;
tray_z = 11.4;
tray_t = 1.4;
strap_w = 24.4;
strap_gap = 3.2;
strap_y = -1.78;
strap_out = 6.3;
lid_screw_x = [4.0, outer_x - 4.0];
lid_screw_y = [4.3, outer_y - 4.3];

module rr(x,y,z,w,d,h,r) {
    translate([x,y,z]) linear_extrude(height=h)
        hull() for (a=[r,w-r], b=[r,d-r])
            translate([a,b]) circle(r=r);
}
module screw_positions() {
    for (x=lid_screw_x, y=lid_screw_y) translate([x,y,0]) children();
}
module cable_slots() {
    // Opposing top edge passes: USB-C plug / buttons, to verify on actual board.
    for (x=[-eps,outer_x-wall-eps])
        translate([x,(outer_y-slot_width)/2,outer_z-slot_height])
            cube([wall+2*eps,slot_width,slot_height+eps]);
}
module shape_limit() {
    rr(0,0,-eps,outer_x,outer_y,outer_z+eps*2,2.2);
}
module box() {
    difference() {
        // Original lower enclosure. Feet removed so the case prints bottom down.
        union() {
            intersection() {
                cube([outer_x,outer_y,outer_z]);
                shape_limit();
            }
            for (flip=[false,true])
                if (flip) translate([0,outer_y,0]) mirror([0,1,0]) strap_eye();
                else strap_eye();
        }
        // Upstream box cavity; vents relocated away from the battery.
        translate([wall,wall,base_thickness]) cube([inner_x,inner_y,inner_z+eps]);
        cable_slots();
        for (x=[8.3,36.5], y=[38.9,41.6,44.3,47.0])
            rr(x,y,-eps,4.8,1.5,base_thickness+2*eps,0.7);
    }
}
module strap_eye() {
    // One-piece closed crossbar; root overlaps wall. Vertical slot prints flat.
    x = (outer_x-34.6)/2;
    h = 5.6;
    w = 34.6;
    d = strap_out+2.1;
    translate([0,0,0]) difference() {
        union() {
            rr(x,-strap_out,0,w,d,h,1.65);
            for (xx=[x+0.15, x+w-4.3])
                hull() {
                    translate([xx,-3.8,5.0]) cube([4.15,4.9,0.6]);
                    translate([xx,0.15,8.2]) cube([4.15,1.85,0.25]);
                }
        }
        // Flared upper and lower entries so the narrow part has no sharp edge.
        rr((outer_x-strap_w)/2,strap_y-strap_gap/2,-eps,
           strap_w,strap_gap,h+2*eps,0.68);
        for (z=[0,h])
            hull() {
                rr((outer_x-strap_w-1)/2,strap_y-(strap_gap+1)/2,z-eps,
                   strap_w+1,strap_gap+1,2*eps,0.92);
                rr((outer_x-strap_w)/2,strap_y-strap_gap/2,
                   z == 0 ? 0.50 : h-0.50,strap_w,strap_gap,eps,0.68);
            }
    }
}
module seat_rail(front=true) {
    // Wedge grows inward gradually. If moved, recheck room for the cell.
    if (!front) translate([0,outer_y,0]) mirror([0,1,0]) seat_rail();
    else for (x=[5,31.6]) hull() {
        translate([x,1.8,10.05]) cube([12.9,0.7,0.08]);
        translate([x,1.8,tray_z-0.25]) cube([12.9,1.75,0.25]);
    }
}
module mount_boss() {
    // Pillar flares out of the short side wall, clear of the board and cell.
    for (i=[0,1], j=[0,1]) {
        x=lid_screw_x[i]; y=lid_screw_y[j];
        difference() {
            hull() {
                translate([x,j == 0 ? 1.8 : outer_y-2.35,12.9])
                    cube([0.3,0.6,0.1],center=false);
                translate([x,y,16.9]) cylinder(d=4.6,h=outer_z-16.9);
                translate([x,j == 0 ? 1.8 : outer_y-1.8,16.9])
                    cylinder(d=2,h=outer_z-16.9);
            }
            translate([x,y,15.4]) cylinder(d=1.65,h=outer_z-15.4+eps);
        }
    }
}
module shell() {
    union() {
        box();
        seat_rail();
        seat_rail(false);
        mount_boss();
        // Short sound standoffs, outside the battery footprint.
        for (x=[7.0,41.1])
            translate([x,37.0,base_thickness-eps]) cube([1.15,13.4,0.7+eps]);
    }
}
module lid(trial=false) {
    // Preserves the top plate and locating lip of the upstream lid; breaks
    // the lip into two tabs so it cannot block the two side openings.
    difference() {
        union() {
            rr(0,0,lid_lip,outer_x,outer_y,lid_plate,2.2);
            for (y=[wall+tolerance,outer_y-wall-tolerance-1.0])
                translate([11,y,0]) cube([outer_x-22,1.0,lid_lip+eps]);
        }
        if(trial)
            rr((outer_x-41.2)/2,(outer_y-41.2)/2,-eps,41.2,41.2,lid_plate+lid_lip+2*eps,1.4);
        else
            rr((outer_x-31)/2,(outer_y-23)/2+8,-eps,31,23,lid_plate+lid_lip+2*eps,1.15);
        screw_positions() translate([0,0,lid_lip-eps]) cylinder(d=2.35,h=lid_plate+2*eps);
    }
}
module print_lid(trial=false) {
    translate([0,outer_y,lid_lip+lid_plate]) rotate([180,0,0]) lid(trial);
}
module tray() {
    // Flat tray, with four fins locating bare PCB. Two slots for the wires.
    difference() {
        union() {
            rr(3.0,3.0,0,outer_x-6,outer_y-6,tray_t,1.0);
            for (x=[3.15,outer_x-4.35],y=[8.0,outer_y-13.0])
                translate([x,y,tray_t-eps]) cube([1.2,5,1.1+eps]);
            for (x=[11.0,32.6],y=[5.0,outer_y-6.0])
                translate([x,y,tray_t-eps]) cube([6,1,1.1+eps]);
        }
        // Clearance for the overhanging screw bosses during vertical insertion.
        screw_positions() translate([0,0,-eps]) cylinder(r=2.85,h=tray_t+2*eps);
        for (x=[8.8,outer_x-15.8], y=[2.92,outer_y-5.97])
            rr(x,y,-eps,7,3.05,tray_t+2*eps,0.8);
    }
}
module gauge() {
    // Quick fit for bare PCB, and a separate strap-slot gauge in the same piece.
    difference() {
        rr(0,0,0,46,53,1.8,2);
        rr(2.4,2.4,-eps,41.2,41.2,1.8+2*eps,0.8);
        rr((46-strap_w)/2,46.5,-eps,strap_w,strap_gap,1.8+2*eps,0.68);
    }
}
if (part == "shell") shell();
if (part == "bezel") print_lid(false);
if (part == "trial") print_lid(true);
if (part == "tray") tray();
if (part == "gauge") gauge();
if (part == "assembled") {
    color("#23536b") shell();
    color("#51778e") translate([0,0,tray_z]) tray();
    color("#148690") translate([0,0,outer_z-lid_lip]) lid(false);
}
