/// Person module.
pub mod person {
    /// Person struct.
    pub struct Person {
        pub name: String,
        pub age: u32,
    }

    impl Person {
        pub fn new(name: String, age: u32) -> Self {
            Self { name, age }
        }

        pub fn greet(&self) -> String {
            format!("Hello, {}", self.name)
        }
    }
}

/// Repository trait.
pub trait Repository<T> {
    fn get_by_id(&self, id: u32) -> Result<T, String>;
    fn save(&self, entity: T) -> Result<(), String>;
}

/// Status enum.
pub enum Status {
    Active,
    Inactive,
    Pending,
}

/// Utility function.
pub fn create_person(name: &str, age: u32) -> person::Person {
    person::Person::new(name.to_string(), age)
}

/// Generic struct.
pub struct Container<T> {
    pub value: T,
}
