use rand::{rngs::SmallRng, Rng, SeedableRng};

#[cfg(feature = "heavy-testing")]
const NB_ITER: usize = 10000000;

#[cfg(not(feature = "heavy-testing"))]
const NB_ITER: usize = 1000000;

fn create_property_based_test<T: Fn(&mut SmallRng)>(reg: &[u64], f: T) {
    let mut seed_rng = rand::rng();
    for i in 0..NB_ITER {
        let seed = if let Some(&s) = reg.get(i) {
            s
        } else {
            seed_rng.random()
        };

        let mut rng = SmallRng::seed_from_u64(seed);
        f(&mut rng);
    }
}

#[test]
fn test_unload() {
    create_property_based_test(&[], |rng| {
        use simeis_data::ship::{cargo::ShipCargo, resources::Resource};

        let mut cargo = ShipCargo::with_capacity(100.0);
        let res = Resource::Iron;

        let amnt = rng.random_range(1.0..10.0);
        cargo.add_resource(&res, amnt);

        let unload_amnt = rng.random_range(0.0..=amnt);
        let unloaded = cargo.unload(&res, unload_amnt);

        assert!(unloaded <= amnt);
        assert!((cargo.usage - (res.volume() * (amnt - unloaded))).abs() < 1e-3);
    });
}
