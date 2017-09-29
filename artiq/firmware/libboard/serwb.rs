use csr;

pub fn wait_init() {
    info!("waiting for AMC/RTM serwb bridge to be ready...");
    unsafe {
        while csr::serwb_phy::control_ready_read() != 0 {}
    }
    info!("done.");

    // Try reading the identifier register on the other side of the bridge.
    let rtm_identifier = unsafe {
        csr::rtm_identifier::identifier_read()
    };
    if rtm_identifier != 0x5352544d {
        error!("incorrect RTM identifier: 0x{:08x}", rtm_identifier);
        // proceed anyway
    }
}
