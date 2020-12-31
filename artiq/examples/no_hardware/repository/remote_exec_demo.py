import time
import inspect

from sipyco.remote_exec import connect_global_rpc

from artiq.experiment import *

import remote_exec_processing


class RemoteExecDemo(EnvExperiment):
    def build(self):
        self.setattr_device("camera_sim")
        self.setattr_device("scheduler")
        self.setattr_argument("remote_exec", BooleanValue(False))
        self.setattr_argument("show_picture", BooleanValue(True), "Local options")
        self.setattr_argument("enable_fit", BooleanValue(True), "Local options")
        if self.remote_exec:
            self.setattr_device("camera_sim_rexec")

    def prepare(self):
        if self.remote_exec:
            connect_global_rpc(self.camera_sim_rexec)
            self.camera_sim_rexec.add_code(
                inspect.getsource(remote_exec_processing))

    def transfer_parameters(self, parameters):
        w, h, cx, cy = parameters
        self.set_dataset("rexec_demo.gaussian_w", w, archive=False, broadcast=True)
        self.set_dataset("rexec_demo.gaussian_h", h, archive=False, broadcast=True)
        self.set_dataset("rexec_demo.gaussian_cx", cx, archive=False, broadcast=True)
        self.set_dataset("rexec_demo.gaussian_cy", cy, archive=False, broadcast=True)

    def fps_meter(self):
        t = time.monotonic()
        if hasattr(self, "last_pt_update"):
            self.iter_count += 1
            dt = t - self.last_pt_update
            if dt >= 5:
                pt = dt/self.iter_count
                self.set_dataset("rexec_demo.picture_pt", pt, archive=False, broadcast=True)
                self.last_pt_update = t
                self.iter_count = 0
        else:
            self.last_pt_update = t
            self.iter_count = 0

    def run_local(self):
        while True:
            self.fps_meter()
            data = self.camera_sim.get_picture()
            if self.show_picture:
                self.set_dataset("rexec_demo.picture", data,
                                 archive=False, broadcast=True)
            if self.enable_fit:
                p = remote_exec_processing.fit(data, self.get_dataset)
                self.transfer_parameters(p)
            self.scheduler.pause()

    def run_remote(self):
        while True:
            self.fps_meter()
            p = self.camera_sim_rexec.call("get_and_fit")
            self.transfer_parameters(p)
            self.scheduler.pause()

    def run(self):
        try:
            if self.remote_exec:
                self.run_remote()
            else:
                self.run_local()
        except TerminationRequested:
            pass
